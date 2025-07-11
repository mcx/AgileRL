import copy
from collections import OrderedDict
from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple, TypeVar, Union

import torch
import torch.nn as nn
from gymnasium import spaces

from agilerl.modules import EvolvableCNN, EvolvableLSTM, EvolvableMLP
from agilerl.modules.base import EvolvableModule, ModuleDict, MutationType, mutation
from agilerl.modules.configs import CnnNetConfig, MlpNetConfig, NetConfig
from agilerl.typing import ArrayOrTensor, ConfigType, ModuleType, NetConfigType
from agilerl.utils.evolvable_networks import (
    get_activation,
    is_image_space,
    is_vector_space,
    tuple_to_dict_space,
)

SelfMultiInput = TypeVar("SelfMultiInput", bound="EvolvableMultiInput")
SupportedEncoderTypes = Union[EvolvableCNN, EvolvableMLP, EvolvableLSTM, SelfMultiInput]
MultiInputConfigType = Union[ConfigType, Dict[str, ConfigType]]
TupleOrDictSpace = Union[spaces.Tuple, spaces.Dict]
TupleOrDictObservation = Union[Dict[str, ArrayOrTensor], Tuple[ArrayOrTensor]]

# Default configurations for the feature extractors
DefaultCnnConfig = CnnNetConfig(
    channel_size=[16, 16],
    kernel_size=[3, 3],
    stride_size=[1, 1],
    output_activation="ReLU",
)
DefaultMlpConfig = MlpNetConfig(
    hidden_size=[64, 64],
    output_activation="ReLU",
    output_layernorm=True,
)


def get_total_flatdim(observation_spaces: spaces.Dict) -> int:
    """Get the total flat dimension of the observation space.

    :param observation_space: Dictionary or Tuple space of observations.
    :type observation_space: spaces.Dict or spaces.Tuple
    :return: Total flat dimension of the observation space.
    """
    return sum([spaces.flatdim(space) for space in observation_spaces.spaces.values()])


def vector_space_check(space: spaces.Space) -> bool:
    """Check if the space is a vector space as it pertains to the use of
    an EvolvableMLP.

    :param space: Input space
    :type space: spaces.Space
    :return: True if the space is a vector space, False otherwise
    """
    return is_vector_space(space) or (
        isinstance(space, spaces.Box) and len(space.shape) > 3
    )


class EvolvableMultiInput(EvolvableModule):
    """Evolvable multi-input network for Tuple or Dict observation spaces. It inspects the
    observation space to determine the type of network to build for each key. It builds an
    ``EvolvableCNN`` for image subspaces and a nn.Flatten() for other types. Vector observations are
    concatenated with the extracted features before passing through an ``EvolvableMLP`` to produce
    the output tensor. Optionally, users may specify an additional ``EvolvableMLP`` to be applied to
    the concatenated vector observations before concatenation with the extracted features.

    Supports the following types of architecture mutations during training:

    * Adding or removing latent nodes
    * Inherits the mutation methods of any nested ``EvolvableModule`` objects used in the network

    :param observation_space: Dictionary or Tuple space of observations.
    :type observation_space: spaces.Dict or spaces.Tuple
    :param num_outputs: Dimension of the output tensor.
    :type num_outputs: int
    :param latent_dim: Dimension of the latent space representation. Default is 16.
    :type latent_dim: int, optional
    :param vector_space_mlp: Whether to use an MLP for the vector spaces. This is done by concatenating the
        flattened observations and passing them through an `EvolvableMLP`. Default is False, whereby the
        observations are concatenated directly to the feature encodings before the final MLP.
    :type vector_space_mlp: bool, optional
    :param cnn_config: Configuration for the CNN feature extractor. Default is None.
    :type cnn_config: MultiInputConfigType, optional
    :param mlp_config: Configuration for the MLP feature extractor. Default is None.
    :type mlp_config: MultiInputConfigType, optional
    :param init_dicts: Dictionary of initialization dictionaries for the feature extractors. Default is {}.
    :type init_dicts: Dict[str, Dict[str, Any]], optional
    :param output_activation: Activation function for the output layer. Default is None.
    :type output_activation: Optional[str], optional
    :param min_latent_dim: Minimum dimension of the latent space. Default is 8.
    :type min_latent_dim: int, optional
    :param max_latent_dim: Maximum dimension of the latent space. Default is 128.
    :type max_latent_dim: int, optional
    :param device: Device to use for the network. Default is "cpu".
    :type device: str, optional
    :param name: Name of the network. Default is "multi_input".
    :type name: str, optional
    :param random_seed: Random seed to use for the network. Defaults to None.
    :type random_seed: Optional[int]
    """

    feature_net: ModuleDict

    def __init__(
        self,
        observation_space: TupleOrDictSpace,
        num_outputs: int,
        latent_dim: int = 32,
        vector_space_mlp: bool = False,
        cnn_config: Optional[MultiInputConfigType] = None,
        mlp_config: Optional[MultiInputConfigType] = None,
        init_dicts: Optional[MultiInputConfigType] = None,
        output_activation: Optional[str] = None,
        output_layernorm: bool = False,
        min_latent_dim: int = 8,
        max_latent_dim: int = 128,
        device: str = "cpu",
        name: str = "multi_input",
        random_seed: Optional[int] = None,
    ):
        super().__init__(device, random_seed)

        assert num_outputs > 0, "Number of outputs must be greater than 0."
        assert latent_dim > 0, "Latent dimension must be greater than 0."
        assert isinstance(
            observation_space, (spaces.Dict, spaces.Tuple)
        ), "Observation space must be a Dict or Tuple space."
        assert (
            latent_dim <= max_latent_dim
        ), "Latent dimension must be less than or equal to max latent dimension."
        assert (
            latent_dim >= min_latent_dim
        ), "Latent dimension must be greater than or equal to min latent dimension."

        # Convert Tuple space to Dict space for consistency
        self.is_tuple_space = False
        if isinstance(observation_space, spaces.Tuple):
            observation_space = tuple_to_dict_space(observation_space)
            self.is_tuple_space = True

        self.observation_space = observation_space
        self.num_outputs = num_outputs
        self.cnn_config = cnn_config or DefaultCnnConfig
        self.mlp_config = mlp_config or DefaultMlpConfig
        self._init_dicts = init_dicts or {}
        self._activation = None
        self.mlp_name = None
        self.vector_space_mlp = vector_space_mlp
        self.latent_dim = latent_dim
        self.output_activation = output_activation
        self.min_latent_dim = min_latent_dim
        self.max_latent_dim = max_latent_dim
        self.name = name
        self.device = device

        # We use an output nn.LayerNorm whenever specified, or if there is an MLP
        # feature extractor that uses layer_norm=True
        self.output_layernorm = output_layernorm or (
            self.vector_space_mlp and self.mlp_config.get("layer_norm", True)
        )

        # Modifications for MLP encoders
        if self.vector_space_mlp:
            self._modify_mlp_config()

        # Vector spaces
        self.vector_spaces = spaces.Dict(
            {
                key: space
                for key, space in observation_space.spaces.items()
                if vector_space_check(space)
            }
        )
        self.total_vector_dims = get_total_flatdim(self.vector_spaces)

        # Build feature extractor
        self.feature_net = self.build_feature_extractor()

        # Calculate total extracted features from non-vector spaces
        # (i.e. Box spaces with more than one dimension)
        self.extracted_features_dim = self.calc_extracted_features_dim()

        # Vector observations (i.e. 1D Box, Discrete, MultiDiscrete) are either
        # passed through an MLP or concatenated directly to the extracted features
        features_dim = self.extracted_features_dim + self.total_vector_dims * (
            1 - self.vector_space_mlp
        )
        # Final dense layer to convert feature encodings to desired num_outputs
        self.final_dense = nn.Linear(features_dim, num_outputs, device=device)
        self.final_layernorm = (
            nn.LayerNorm(num_outputs, device=device, elementwise_affine=False)
            if self.output_layernorm
            else None
        )
        self.output = get_activation(output_activation)

    @property
    def net_config(self) -> Dict[str, Any]:
        """Returns the configuration of the network.

        :return: Network configuration
        :rtype: Dict[str, Any]
        """
        net_config = self.init_dict.copy()
        for attr in ["observation_space", "num_outputs", "device", "name"]:
            net_config.pop(attr)
        return net_config

    @property
    def activation(self) -> str:
        """Get the activation function for the network.

        :return: Activation function
        :rtype: str
        """
        return self._activation

    @activation.setter
    def activation(self, activation: str) -> None:
        """Set the activation function for the network.

        :param activation: Activation function to use.
        :type activation: str
        """
        self._activation = activation
        self.feature_net.change_activation(activation, output=True)

    @property
    def init_dicts(self) -> Dict[str, Dict[str, Any]]:
        """Returns the initialization dictionaries for the network.

        :return: Initialization dictionaries
        :rtype: Dict[str, Dict[str, Any]]
        """
        if not hasattr(self, "feature_net"):
            return self._init_dicts

        reformatted_dicts = {}
        for key, net in self.feature_net.modules().items():
            init_dict = net.init_dict
            init_dict.pop("observation_space", None)  # MultiInput
            init_dict.pop("input_size", None)  # LSTM
            init_dict.pop("input_shape", None)  # CNN
            init_dict.pop("num_inputs", None)  # MLP
            init_dict["num_outputs"] = self.latent_dim
            reformatted_dicts[key] = init_dict

        return reformatted_dicts

    @property
    def cnn_init_dict(self) -> Dict[str, Any]:
        """Returns the initialization dictionary for the CNN."""
        return copy.deepcopy(self.cnn_config)

    @property
    def mlp_init_dict(self) -> Dict[str, Any]:
        """Returns the initialization dictionary for the MLP."""
        return copy.deepcopy(self.mlp_config)

    def _reformat_mlp_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Reformats the MLP configuration."""
        config["output_vanish"] = False  # Don't want output vanish for encoder
        config["output_layernorm"] = config.get(
            "layer_norm", True
        )  # Add layer norm for output if present generally
        config["output_activation"] = config.get(
            "activation", "ReLU"
        )  # Use same output activation
        return config

    def _modify_mlp_config(self) -> None:
        """Modifies the MLP architecture to be appropriate for use as an encoder (i.e. disable
        output vanishing, and apply layer normalization at the final layer consistently with the
        rest of the network). See https://github.com/AgileRL/AgileRL/issues/337 for more details.
        """
        self.mlp_config["output_vanish"] = False
        self.mlp_config["output_layernorm"] = self.mlp_config.get("layer_norm", True)
        self.mlp_config["output_activation"] = self.mlp_config.get("activation", "ReLU")

    def init_weights_gaussian(
        self, std_coeff: float = 4, output_coeff: float = 4
    ) -> None:
        """Initialise weights of linear layers using Gaussian distribution."""
        for module in self.feature_net.modules().values():
            module.init_weights_gaussian(std_coeff=std_coeff)

        # Initialise final dense layer
        EvolvableModule.init_weights_gaussian(self.final_dense, std_coeff=output_coeff)

    def calc_extracted_features_dim(self) -> int:
        """Calculates the toal dimension of the features extracted by the evolvable
        feature extractors.

        :return: Total dimension of the extracted features.
        :rtype: int
        """
        return sum(
            [
                self.latent_dim
                for name in self.feature_net.keys()
                if name not in self.vector_spaces.keys()
            ]
        )

    def get_inner_init_dict(self, key: str, default: ModuleType) -> NetConfigType:
        """Returns the initialization dictionary for the specified key.

        :param key: Key of the observation space.
        :type key: str
        :param default: Default value to return if the key is not found.
        :type default: ModuleType
        :return: Initialization dictionary.
        :rtype: ConfigType
        """
        init_dicts = self.init_dicts
        if key in init_dicts:
            init_dict = init_dicts[key]
            init_dict["num_outputs"] = self.latent_dim
            init_dict["device"] = self.device
            return init_dict

        init_dict = {
            ModuleType.CNN: self.cnn_init_dict,
            ModuleType.MLP: self.mlp_init_dict,
            ModuleType.MULTI_INPUT: self.net_config,
        }.get(default)

        if init_dict is None:
            raise ValueError(
                "Invalid default value provided, must be 'cnn' or 'mlp' or 'multi_input'."
            )
        else:
            # Check if we are extracting a nested dict
            nested_dict = init_dict.get(key)
            init_dict = (
                copy.deepcopy(nested_dict)
                if nested_dict is not None
                else copy.deepcopy(init_dict)
            )

            if isinstance(init_dict, NetConfig):
                init_dict = asdict(init_dict)

        init_dict["num_outputs"] = self.latent_dim
        init_dict["device"] = self.device
        return init_dict

    def build_feature_extractor(self) -> Dict[str, SupportedEncoderTypes]:
        """Creates the feature extractor and final MLP networks.

        :return: Dictionary of feature extractors.
        :rtype: Dict[str, EvolvableMLP | EvolvableCNN | EvolvableLSTM | EvolvableMultiInput]
        """
        # Automatically build feature extractors from subspaces
        feature_net = ModuleDict(device=self.device)
        for key, space in self.observation_space.spaces.items():
            if isinstance(space, spaces.Box) and len(space.shape) in [0, 1]:
                continue

            # EvolvableMultiInput for nested multi-input spaces
            if isinstance(space, (spaces.Dict, spaces.Tuple)):
                init_dict = self.get_inner_init_dict(
                    key, default=ModuleType.MULTI_INPUT
                )
                feature_extractor = EvolvableMultiInput(
                    observation_space=space,
                    name=init_dict.pop("name", key),
                    **init_dict,
                )

            # EvolvableCNN for image spaces
            elif is_image_space(space):
                init_dict = self.get_inner_init_dict(key, default=ModuleType.CNN)
                feature_extractor = EvolvableCNN(
                    input_shape=space.shape,
                    name=init_dict.pop("name", key),
                    **init_dict,
                )
            else:  # Flatten other observation types
                feature_extractor = nn.Flatten()

            feature_net[key] = feature_extractor

        # Optionally, use an EvolvableMLP for all concatenated vector inputs
        if self.vector_space_mlp:
            init_dict = self.get_inner_init_dict("vector_mlp", default=ModuleType.MLP)

            self.mlp_name = init_dict.pop("name", "vector_mlp")
            vector_mlp = EvolvableMLP(
                num_inputs=self.total_vector_dims, name=self.mlp_name, **init_dict
            )
            feature_net[self.mlp_name] = vector_mlp

        return feature_net

    def forward(self, x: TupleOrDictObservation) -> torch.Tensor:
        """Forward pass of the composed network. Extracts features from each observation key and concatenates
        them with the corresponding observation key if specified. The concatenated features are then passed
        through the final MLP to produce the output tensor.

        :param x: Dictionary of observations.
        :type x: Dict[str, ArrayOrTensor], Tuple[ArrayOrTensor]
        :return: Output tensor.
        :rtype: torch.Tensor
        """
        if isinstance(x, tuple):
            x = dict(zip(self.observation_space.spaces.keys(), x))

        for key, obs in x.items():
            if not isinstance(obs, torch.Tensor):
                x[key] = torch.tensor(obs, device=self.device, dtype=torch.float32)

        # Extract features from non-vector subspaces
        extracted_features = OrderedDict()
        if self.extracted_features_dim > 0:
            for key in x.keys():
                if key in self.feature_net.keys():
                    extracted_features[key] = self.feature_net[key](x[key])

        # Extract raw features from vector spaces
        vector_inputs = []
        for key, space in self.vector_spaces.items():
            _obs = (
                extracted_features.pop(key)
                if key in extracted_features.keys()
                else x[key]
            )
            if len(_obs.shape) == 1:
                dim = len(space.shape) - 1
                _obs = _obs.unsqueeze(dim)

            vector_inputs.append(_obs)

        # Concatenate vector inputs and, optionally, pass through additional EvolvableMLP
        vector_inputs = (
            torch.cat(vector_inputs, dim=1)
            if vector_inputs
            else torch.tensor([], device=self.device)
        )
        vector_features = (
            self.feature_net[self.mlp_name](vector_inputs)
            if self.vector_space_mlp
            else vector_inputs
        )

        # Concatenate extracted latent features
        extracted_features = (
            torch.cat(list(extracted_features.values()), dim=1)
            if extracted_features
            else torch.tensor([], device=self.device)
        )

        # Concatenate all features and pass through final MLP
        features = torch.cat([extracted_features, vector_features], dim=1)
        latent = self.final_dense(features)

        if self.output_layernorm:
            latent = self.final_layernorm(latent)

        return self.output(latent)

    @mutation(MutationType.ACTIVATION)
    def change_activation(self, activation: str, output: bool = False) -> None:
        """Set the activation function for the network.

        :param activation: Activation function to use.
        :type activation: str
        :param output: Flag indicating whether to set the output activation function, defaults to False
        :type output: bool, optional

        :return: Activation function
        :rtype: str
        """
        self.activation = activation
        if output:
            self.output = get_activation(activation)

    @mutation(MutationType.NODE)
    def add_latent_node(self, numb_new_nodes: Optional[int] = None) -> Dict[str, Any]:
        """Add a latent node to the network.

        :param numb_new_nodes: Number of new nodes to add, defaults to None
        :type numb_new_nodes: int, optional

        :return: Dictionary specifying the number of nodes added.
        :rtype: Dict[str, Any]
        """
        if numb_new_nodes is None:
            numb_new_nodes = self.rng.choice([8, 16, 32])

        if self.latent_dim + numb_new_nodes < self.max_latent_dim:
            self.latent_dim += numb_new_nodes

        return {"numb_new_nodes": numb_new_nodes}

    @mutation(MutationType.NODE)
    def remove_latent_node(
        self, numb_new_nodes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Remove a latent node from the network.

        :param numb_new_nodes: Number of nodes to remove, defaults to None
        :type numb_new_nodes: int, optional

        :return: Dictionary specifying the number of nodes removed.
        :rtype: Dict[str, Any]
        """
        if numb_new_nodes is None:
            numb_new_nodes = self.rng.choice([8, 16, 32])

        if self.latent_dim - numb_new_nodes > self.min_latent_dim:
            self.latent_dim -= numb_new_nodes

        return {"numb_new_nodes": numb_new_nodes}

    def recreate_network(self) -> None:
        """Recreates the network with the new latent dimension."""
        feature_net = self.build_feature_extractor()
        self.feature_net = EvolvableModule.preserve_parameters(
            old_net=self.feature_net, new_net=feature_net
        )

        # Calculate total extracted features dimension
        extracted_features_dim = self.calc_extracted_features_dim()
        features_dim = extracted_features_dim + self.total_vector_dims * (
            1 - self.vector_space_mlp
        )
        final_dense = nn.Linear(features_dim, self.num_outputs, device=self.device)
        self.final_dense = EvolvableModule.preserve_parameters(
            old_net=self.final_dense, new_net=final_dense
        )
