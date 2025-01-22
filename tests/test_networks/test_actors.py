import pytest
from gymnasium import spaces
import torch
import torch.nn.functional as F

from agilerl.networks.base import EvolvableNetwork
from agilerl.modules.base import EvolvableModule
from agilerl.modules.multi_input import EvolvableMultiInput
from agilerl.modules.mlp import EvolvableMLP
from agilerl.modules.cnn import EvolvableCNN
from agilerl.networks.actors import DeterministicActor, StochasticActor

from tests.helper_functions import (
    generate_dict_or_tuple_space,
    generate_discrete_space,
    generate_random_box_space,
    check_equal_params_ind,
    assert_close_dict
)

@pytest.mark.parametrize(
    "observation_space, action_space, encoder_type",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,)), "multi_input"),
        (generate_discrete_space(4), generate_random_box_space((4,)), "mlp"),
        (generate_random_box_space((8,)), generate_random_box_space((4,)), "mlp"),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,)), "cnn"),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4), "multi_input"),
        (generate_discrete_space(4), generate_discrete_space(4), "mlp"),
        (generate_random_box_space((8,)), generate_discrete_space(4), "mlp"),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4), "cnn"),
    ]
)
def test_deterministic_actor_initialization(observation_space, action_space, encoder_type):
    network = DeterministicActor(observation_space, action_space)

    assert network.observation_space == observation_space

    if encoder_type == "multi_input":
        assert isinstance(network.encoder, EvolvableMultiInput)
    elif encoder_type == "mlp":
        assert isinstance(network.encoder, EvolvableMLP)
    elif encoder_type == "cnn":
        assert isinstance(network.encoder, EvolvableCNN)

@pytest.mark.parametrize(
    "observation_space, action_space",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,))),
        (generate_discrete_space(4), generate_random_box_space((4,))),
        (generate_random_box_space((8,)), generate_random_box_space((4,))),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,))),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4)),
        (generate_discrete_space(4), generate_discrete_space(4)),
        (generate_random_box_space((8,)), generate_discrete_space(4)),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4)),
    ]
)
def test_deterministic_actor_mutation_methods(observation_space, action_space):
    network = DeterministicActor(observation_space, action_space)

    for method in network.mutation_methods:
        new_network = network.clone() 
        getattr(new_network, method)()

        if "." in method:
            net_name = method.split(".")[0]
            mutated_module: EvolvableModule = getattr(new_network, net_name)
            exec_method = new_network.last_mutation_attr.split(".")[-1]

            if isinstance(observation_space, (spaces.Tuple, spaces.Dict)):
                mutated_attr = mutated_module.last_mutation_attr.split(".")[-1]
            else:
                mutated_attr = mutated_module.last_mutation_attr

            assert mutated_attr == exec_method
        
        check_equal_params_ind(network, new_network)

@pytest.mark.parametrize(
    "observation_space, action_space",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,))),
        (generate_discrete_space(4), generate_random_box_space((4,))),
        (generate_random_box_space((8,)), generate_random_box_space((4,))),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,))),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4)),
        (generate_discrete_space(4), generate_discrete_space(4)),
        (generate_random_box_space((8,)), generate_discrete_space(4)),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4)),
    ]
)
def test_deterministic_actor_forward(observation_space: spaces.Space, action_space: spaces.Space):
    network = DeterministicActor(observation_space, action_space)

    x_np = observation_space.sample()

    if isinstance(observation_space, spaces.Discrete):
        x_np = F.one_hot(torch.tensor(x_np), num_classes=observation_space.n).float().numpy()

    with torch.no_grad():
        out = network(x_np)

    assert isinstance(out, torch.Tensor)
    assert out.shape == torch.Size([1, spaces.flatdim(action_space)])

    if isinstance(observation_space, spaces.Dict):
        x = {key: torch.tensor(value) for key, value in x_np.items()}
    elif isinstance(observation_space, spaces.Tuple):
        x = tuple(torch.tensor(value) for value in x_np)
    else:
        x = torch.tensor(x_np)
    
    with torch.no_grad():
        out = network(x)

    assert isinstance(out, torch.Tensor)
    assert out.shape == torch.Size([1, spaces.flatdim(action_space)])

@pytest.mark.parametrize(
    "observation_space, action_space",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,))),
        (generate_discrete_space(4), generate_random_box_space((4,))),
        (generate_random_box_space((8,)), generate_random_box_space((4,))),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,))),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4)),
        (generate_discrete_space(4), generate_discrete_space(4)),
        (generate_random_box_space((8,)), generate_discrete_space(4)),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4)),
    ]
)
def test_deterministic_actor_clone(observation_space: spaces.Space, action_space: spaces.Space):
    network = DeterministicActor(observation_space, action_space)

    original_net_dict = dict(network.named_parameters())
    clone = network.clone()
    assert isinstance(clone, EvolvableNetwork)

    assert_close_dict(network.init_dict, clone.init_dict)

    assert str(clone.state_dict()) == str(network.state_dict())
    for key, param in clone.named_parameters():
        torch.testing.assert_close(param, original_net_dict[key])

@pytest.mark.parametrize(
    "observation_space, action_space, encoder_type",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,)), "multi_input"),
        (generate_discrete_space(4), generate_random_box_space((4,)), "mlp"),
        (generate_random_box_space((8,)), generate_random_box_space((4,)), "mlp"),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,)), "cnn"),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4), "multi_input"),
        (generate_discrete_space(4), generate_discrete_space(4), "mlp"),
        (generate_random_box_space((8,)), generate_discrete_space(4), "mlp"),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4), "cnn"),
    ]
)
def test_stochastic_actor_initialization(observation_space, action_space, encoder_type):
    network = StochasticActor(observation_space, action_space)

    assert network.observation_space == observation_space

    if encoder_type == "multi_input":
        assert isinstance(network.encoder, EvolvableMultiInput)
    elif encoder_type == "mlp":
        assert isinstance(network.encoder, EvolvableMLP)
    elif encoder_type == "cnn":
        assert isinstance(network.encoder, EvolvableCNN)

@pytest.mark.parametrize(
    "observation_space, action_space",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,))),
        (generate_discrete_space(4), generate_random_box_space((4,))),
        (generate_random_box_space((8,)), generate_random_box_space((4,))),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,))),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4)),
        (generate_discrete_space(4), generate_discrete_space(4)),
        (generate_random_box_space((8,)), generate_discrete_space(4)),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4)),
    ]
)
def test_stochastic_actor_mutation_methods(observation_space, action_space):
    network = StochasticActor(observation_space, action_space)

    for method in network.mutation_methods:
        new_network = network.clone() 
        getattr(new_network, method)()

        if "." in method:
            net_name = method.split(".")[0]
            mutated_module: EvolvableModule = getattr(new_network, net_name)
            exec_method = new_network.last_mutation_attr.split(".")[-1]

            if isinstance(observation_space, (spaces.Tuple, spaces.Dict)):
                mutated_attr = mutated_module.last_mutation_attr.split(".")[-1]
            else:
                mutated_attr = mutated_module.last_mutation_attr

            assert mutated_attr == exec_method
        
        check_equal_params_ind(network, new_network)

@pytest.mark.parametrize(
    "observation_space, action_space",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,))),
        (generate_discrete_space(4), generate_random_box_space((4,))),
        (generate_random_box_space((8,)), generate_random_box_space((4,))),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,))),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4)),
        (generate_discrete_space(4), generate_discrete_space(4)),
        (generate_random_box_space((8,)), generate_discrete_space(4)),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4)),
    ]
)
def test_stochastic_actor_forward(observation_space: spaces.Space, action_space: spaces.Space):
    network = StochasticActor(observation_space, action_space)

    x_np = observation_space.sample()

    if isinstance(observation_space, spaces.Discrete):
        x_np = F.one_hot(torch.tensor(x_np), num_classes=observation_space.n).float().numpy()

    with torch.no_grad():
        dist = network(x_np)

    if isinstance(action_space, spaces.Discrete):
        assert isinstance(dist, torch.distributions.Categorical)
    else:
        assert isinstance(dist, torch.distributions.Normal)

    if isinstance(observation_space, spaces.Dict):
        x = {key: torch.tensor(value) for key, value in x_np.items()}
    elif isinstance(observation_space, spaces.Tuple):
        x = tuple(torch.tensor(value) for value in x_np)
    else:
        x = torch.tensor(x_np)
    
    with torch.no_grad():
        dist = network(x)

    assert isinstance(dist, torch.distributions.Distribution)

@pytest.mark.parametrize(
    "observation_space, action_space",
    [
        (generate_dict_or_tuple_space(2, 3), generate_random_box_space((4,))),
        (generate_discrete_space(4), generate_random_box_space((4,))),
        (generate_random_box_space((8,)), generate_random_box_space((4,))),
        (generate_random_box_space((3, 32, 32)), generate_random_box_space((4,))),
        (generate_dict_or_tuple_space(2, 3), generate_discrete_space(4)),
        (generate_discrete_space(4), generate_discrete_space(4)),
        (generate_random_box_space((8,)), generate_discrete_space(4)),
        (generate_random_box_space((3, 32, 32)), generate_discrete_space(4)),
    ]
)
def test_stochastic_actor_clone(observation_space: spaces.Space, action_space: spaces.Space):
    network = StochasticActor(observation_space, action_space)

    original_net_dict = dict(network.named_parameters())
    clone = network.clone()
    assert isinstance(clone, EvolvableNetwork)

    assert_close_dict(network.init_dict, clone.init_dict)

    assert str(clone.state_dict()) == str(network.state_dict())
    for key, param in clone.named_parameters():
        torch.testing.assert_close(param, original_net_dict[key])
