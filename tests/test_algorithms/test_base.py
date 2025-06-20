from pathlib import Path

import pytest
import torch
import torch.optim as optim
from gymnasium import spaces

from agilerl.algorithms.core import MultiAgentRLAlgorithm, OptimizerWrapper, RLAlgorithm
from agilerl.algorithms.core.registry import (
    HyperparameterConfig,
    NetworkGroup,
    RLParameter,
)
from agilerl.modules import EvolvableCNN, EvolvableMLP, EvolvableMultiInput
from agilerl.utils.evolvable_networks import is_image_space
from tests.helper_functions import (
    gen_multi_agent_dict_or_tuple_spaces,
    generate_dict_or_tuple_space,
    generate_discrete_space,
    generate_multi_agent_box_spaces,
    generate_multi_agent_discrete_spaces,
    generate_multidiscrete_space,
    generate_random_box_space,
    is_processed_observation,
)


@pytest.fixture
def mlp_config():
    return {"hidden_size": [8]}


@pytest.fixture
def cnn_config():
    return {"channel_size": [3], "kernel_size": [3]}


@pytest.fixture
def multi_input_config():
    return {
        "mlp_config": {"hidden_size": [8]},
        "cnn_config": {"channel_size": [3], "kernel_size": [3]},
    }


class DummyRLAlgorithm(RLAlgorithm):
    def __init__(self, observation_space, action_space, index, lr=True, **kwargs):
        super().__init__(observation_space, action_space, index, **kwargs)

        num_outputs = (
            self.action_space.n
            if isinstance(self.action_space, spaces.Discrete)
            else self.action_space.shape[0]
        )
        if is_image_space(self.observation_space):
            self.dummy_actor = EvolvableCNN(
                self.observation_space.shape,
                num_outputs,
                channel_size=[3],
                kernel_size=[3],
                stride_size=[1],
            )
        elif isinstance(self.observation_space, (spaces.Box, spaces.Discrete)):
            num_inputs = (
                self.observation_space.shape[0]
                if isinstance(self.observation_space, spaces.Box)
                else self.observation_space.n
            )
            self.dummy_actor = EvolvableMLP(num_inputs, num_outputs, hidden_size=[8])
        elif isinstance(self.observation_space, spaces.MultiDiscrete):
            # Handle MultiDiscrete spaces
            num_inputs = len(self.observation_space.nvec)
            self.dummy_actor = EvolvableMLP(num_inputs, num_outputs, hidden_size=[8])
        elif isinstance(self.observation_space, (spaces.Dict, spaces.Tuple)):
            config = {
                "mlp_config": {"hidden_size": [8]},
                "cnn_config": {
                    "channel_size": [3],
                    "kernel_size": [3],
                    "stride_size": [1],
                },
            }
            self.dummy_actor = EvolvableMultiInput(
                self.observation_space, num_outputs, **config
            )

        self.lr = 0.1
        self.dummy_optimizer = OptimizerWrapper(optim.Adam, self.dummy_actor, self.lr)
        self.dummy_attribute = "test_value"

        self.register_network_group(NetworkGroup(eval=self.dummy_actor, policy=True))

    def get_action(self, *args, **kwargs):
        return

    def learn(self, *args, **kwargs):
        return

    def test(self, *args, **kwargs):
        return


class DummyMARLAlgorithm(MultiAgentRLAlgorithm):
    def __init__(self, observation_spaces, action_spaces, agent_ids, index, **kwargs):
        super().__init__(observation_spaces, action_spaces, agent_ids, index, **kwargs)

        def create_actor(idx):
            obs_space = self.observation_spaces[idx]
            action_space = self.action_spaces[idx]
            num_outputs = (
                action_space.n
                if isinstance(action_space, spaces.Discrete)
                else action_space.shape[0]
            )
            if is_image_space(obs_space):
                return EvolvableCNN(
                    obs_space.shape,
                    num_outputs,
                    channel_size=[3],
                    kernel_size=[3],
                    stride_size=[1],
                )
            elif isinstance(obs_space, (spaces.Box, spaces.Discrete)):
                num_inputs = (
                    obs_space.shape[0]
                    if isinstance(obs_space, spaces.Box)
                    else obs_space.n
                )
                return EvolvableMLP(num_inputs, num_outputs, hidden_size=[8])
            elif isinstance(obs_space, (spaces.Dict, spaces.Tuple)):
                config = {
                    "mlp_config": {"hidden_size": [8]},
                    "cnn_config": {
                        "channel_size": [3],
                        "kernel_size": [3],
                        "stride_size": [1],
                    },
                }
                return EvolvableMultiInput(obs_space, num_outputs, **config)

        self.dummy_actors = [create_actor(idx) for idx in range(self.n_agents)]
        self.lr = 0.1
        self.dummy_optimizer = OptimizerWrapper(
            optim.Adam, self.dummy_actors, self.lr, multiagent=True
        )

        self.register_network_group(
            NetworkGroup(eval=self.dummy_actors, policy=True, multiagent=True)
        )

    def get_action(self, *args, **kwargs):
        return

    def learn(self, *args, **kwargs):
        return

    def test(self, *args, **kwargs):
        return


@pytest.mark.parametrize(
    "observation_space",
    [
        generate_dict_or_tuple_space(1, 2),
        generate_discrete_space(4),
        generate_random_box_space((4,)),
        # generate_multidiscrete_space(2, 2)
    ],
)
@pytest.mark.parametrize(
    "action_space",
    [
        generate_discrete_space(4),
        generate_random_box_space((4,)),
        # generate_multidiscrete_space(2, 2)
    ],
)
def test_initialise_single_agent(observation_space, action_space):
    agent = DummyRLAlgorithm(observation_space, action_space, index=0)
    assert agent is not None


@pytest.mark.parametrize(
    "observation_space",
    [
        generate_multi_agent_box_spaces(2, (2,)),
        generate_multi_agent_discrete_spaces(2, 4),
        gen_multi_agent_dict_or_tuple_spaces(2, 2, 2),
    ],
)
@pytest.mark.parametrize(
    "action_space",
    [
        generate_multi_agent_discrete_spaces(2, 4),
        generate_multi_agent_box_spaces(2, (2,)),
    ],
)
def test_initialise_multi_agent(observation_space, action_space):
    agent = DummyMARLAlgorithm(
        observation_space, action_space, agent_ids=["agent1", "agent2"], index=0
    )
    assert agent is not None


def test_population_single_agent():
    observation_space = generate_random_box_space((4,))
    action_space = generate_discrete_space(4)
    population = DummyRLAlgorithm.population(10, observation_space, action_space)
    assert len(population) == 10
    for i, agent in enumerate(population):
        assert agent.observation_space == observation_space
        assert agent.action_space == action_space
        assert agent.index == i


def test_population_multi_agent():
    observation_spaces = generate_multi_agent_box_spaces(2, (2,))
    action_spaces = generate_multi_agent_discrete_spaces(2, 4)
    population = DummyMARLAlgorithm.population(
        10, observation_spaces, action_spaces, agent_ids=["agent1", "agent2"]
    )
    assert len(population) == 10
    for i, agent in enumerate(population):
        for j in range(2):
            agent_id = agent.agent_ids[j]
            assert agent.observation_space[agent_id] == observation_spaces[j]
            assert agent.action_space[agent_id] == action_spaces[j]

        assert agent.index == i


@pytest.mark.parametrize(
    "observation_space",
    [
        generate_random_box_space((4,)),
        generate_random_box_space((3, 32, 32)),
        generate_dict_or_tuple_space(1, 1, dict_space=True),
        generate_dict_or_tuple_space(1, 1, dict_space=False),
    ],
)
def test_preprocess_observation(observation_space):
    agent = DummyRLAlgorithm(observation_space, generate_discrete_space(4), index=0)
    observation = agent.preprocess_observation(observation_space.sample())
    assert is_processed_observation(observation, observation_space)


def test_incorrect_hp_config():
    with pytest.raises(AttributeError):
        hp_config = HyperparameterConfig(lr_actor=RLParameter(min=0.1, max=0.2))
        _ = DummyRLAlgorithm(
            generate_random_box_space((4,)),
            generate_discrete_space(4),
            index=0,
            hp_config=hp_config,
        )


@pytest.mark.parametrize(
    "with_hp_config",
    [
        False,
        True,
    ],
)
@pytest.mark.parametrize(
    "observation_space",
    [
        generate_random_box_space((4,)),
        generate_discrete_space(4),
        generate_dict_or_tuple_space(1, 1, dict_space=True),
        generate_dict_or_tuple_space(1, 1, dict_space=False),
        generate_multidiscrete_space(2, 2),
    ],
)
def test_save_load_checkpoint_single_agent(tmpdir, with_hp_config, observation_space):
    action_space = generate_discrete_space(4)
    # Initialize the dummy agent
    hp_config = None
    if with_hp_config:
        hp_config = HyperparameterConfig(lr=RLParameter(min=0.05, max=0.2))
        agent = DummyRLAlgorithm(
            observation_space, action_space, index=0, hp_config=hp_config
        )
    else:
        agent = DummyRLAlgorithm(observation_space, action_space, index=0)

    # Save the checkpoint to a file
    checkpoint_path = Path(tmpdir) / "checkpoint.pth"
    agent.save_checkpoint(checkpoint_path)

    # Load the saved checkpoint file
    checkpoint = torch.load(checkpoint_path, weights_only=False)

    # Check if the loaded checkpoint has the correct keys
    assert "dummy_actor_init_dict" in checkpoint["network_info"]["modules"]
    assert "dummy_actor_state_dict" in checkpoint["network_info"]["modules"]
    assert "dummy_optimizer_state_dict" in checkpoint["network_info"]["optimizers"]
    assert "lr" in checkpoint
    assert "index" in checkpoint
    assert "scores" in checkpoint
    assert "fitness" in checkpoint
    assert "steps" in checkpoint

    # Create a new agent with the same hp_config if needed
    new_agent = DummyRLAlgorithm(
        observation_space,
        action_space,
        index=1,  # Different index to verify it gets overwritten
        hp_config=hp_config,
    )

    # Load checkpoint
    new_agent.load_checkpoint(checkpoint_path)

    # Check if properties and weights are loaded correctly
    assert isinstance(
        new_agent.dummy_actor, (EvolvableMLP, EvolvableCNN, EvolvableMultiInput)
    )
    assert new_agent.lr == agent.lr
    assert str(new_agent.dummy_actor.state_dict()) == str(
        agent.dummy_actor.state_dict()
    )
    assert new_agent.index == agent.index
    assert new_agent.scores == agent.scores
    assert new_agent.fitness == agent.fitness
    assert new_agent.steps == agent.steps


@pytest.mark.parametrize(
    "with_hp_config",
    [
        False,
        True,
    ],
)
@pytest.mark.parametrize(
    "observation_spaces",
    [
        generate_multi_agent_box_spaces(2, (4,)),
        generate_multi_agent_discrete_spaces(2, 4),
        gen_multi_agent_dict_or_tuple_spaces(2, 1, 1, dict_space=True),
        gen_multi_agent_dict_or_tuple_spaces(2, 1, 1, dict_space=False),
    ],
)
def test_save_load_checkpoint_multi_agent(tmpdir, with_hp_config, observation_spaces):
    # Initialize the dummy multi-agent
    agent_ids = ["agent1", "agent2"]
    action_spaces = generate_multi_agent_discrete_spaces(2, 4)

    hp_config = None
    if with_hp_config:
        hp_config = HyperparameterConfig(lr=RLParameter(min=0.05, max=0.2))
        agent = DummyMARLAlgorithm(
            observation_spaces,
            action_spaces,
            agent_ids=agent_ids,
            index=0,
            hp_config=hp_config,
        )
    else:
        agent = DummyMARLAlgorithm(
            observation_spaces, action_spaces, agent_ids=agent_ids, index=0
        )

    # Save the checkpoint to a file
    checkpoint_path = Path(tmpdir) / "checkpoint.pth"
    agent.save_checkpoint(checkpoint_path)

    # Load the saved checkpoint file
    checkpoint = torch.load(checkpoint_path, weights_only=False)

    # Check if the loaded checkpoint has the correct keys
    assert "dummy_actors_init_dict" in checkpoint["network_info"]["modules"]
    assert "dummy_actors_state_dict" in checkpoint["network_info"]["modules"]
    assert "dummy_optimizer_state_dict" in checkpoint["network_info"]["optimizers"]
    assert "lr" in checkpoint
    assert "index" in checkpoint
    assert "scores" in checkpoint
    assert "fitness" in checkpoint
    assert "steps" in checkpoint
    assert "agent_ids" in checkpoint

    # Create a new agent with the same hp_config if needed
    new_agent = DummyMARLAlgorithm(
        observation_spaces,
        action_spaces,
        agent_ids=agent_ids,
        index=1,  # Different index to verify it gets overwritten
        hp_config=hp_config,
    )

    # Load checkpoint
    new_agent.load_checkpoint(checkpoint_path)

    # Check if properties and weights are loaded correctly
    for i in range(len(agent.dummy_actors)):
        assert isinstance(
            new_agent.dummy_actors[i], (EvolvableMLP, EvolvableCNN, EvolvableMultiInput)
        )
        assert str(new_agent.dummy_actors[i].state_dict()) == str(
            agent.dummy_actors[i].state_dict()
        )

    assert new_agent.lr == agent.lr
    assert new_agent.index == agent.index
    assert new_agent.scores == agent.scores
    assert new_agent.fitness == agent.fitness
    assert new_agent.steps == agent.steps
    assert new_agent.agent_ids == agent.agent_ids


@pytest.mark.parametrize(
    "device, with_hp_config",
    [
        ("cpu", False),
        ("cpu", True),
    ],
)
@pytest.mark.parametrize(
    "observation_space",
    [
        generate_random_box_space((4,)),
        generate_discrete_space(4),
        generate_dict_or_tuple_space(1, 1, dict_space=True),
        generate_dict_or_tuple_space(1, 1, dict_space=False),
        generate_multidiscrete_space(2, 2),
    ],
)
@pytest.mark.parametrize(
    "action_space",
    [
        generate_random_box_space((2,)),
        generate_discrete_space(4),
    ],
)
def test_load_from_pretrained_single_agent(
    device, tmpdir, with_hp_config, observation_space, action_space
):
    # Initialize the dummy agent
    hp_config = None
    if with_hp_config:
        hp_config = HyperparameterConfig(lr=RLParameter(min=0.05, max=0.2))
        agent = DummyRLAlgorithm(
            observation_space, action_space, index=0, hp_config=hp_config
        )
    else:
        agent = DummyRLAlgorithm(observation_space, action_space, index=0)

    # Save the checkpoint to a file
    checkpoint_path = Path(tmpdir) / "checkpoint.pth"
    agent.save_checkpoint(checkpoint_path)

    # Create new agent object using the class method
    new_agent = DummyRLAlgorithm.load(checkpoint_path, device=device)

    # Check if properties and weights are loaded correctly
    assert new_agent.observation_space == agent.observation_space
    assert new_agent.action_space == agent.action_space
    assert isinstance(
        new_agent.dummy_actor, (EvolvableMLP, EvolvableCNN, EvolvableMultiInput)
    )
    assert new_agent.lr == agent.lr
    assert str(new_agent.dummy_actor.to("cpu").state_dict()) == str(
        agent.dummy_actor.state_dict()
    )
    assert new_agent.index == agent.index
    assert new_agent.scores == agent.scores
    assert new_agent.fitness == agent.fitness
    assert new_agent.steps == agent.steps


@pytest.mark.parametrize(
    "device, with_hp_config",
    [
        ("cpu", False),
        ("cpu", True),
    ],
)
@pytest.mark.parametrize(
    "observation_spaces",
    [
        generate_multi_agent_box_spaces(2, (4,)),
        generate_multi_agent_discrete_spaces(2, 4),
        gen_multi_agent_dict_or_tuple_spaces(2, 1, 1, dict_space=True),
        gen_multi_agent_dict_or_tuple_spaces(2, 1, 1, dict_space=False),
    ],
)
@pytest.mark.parametrize(
    "action_spaces",
    [
        generate_multi_agent_box_spaces(2, (2,)),
        generate_multi_agent_discrete_spaces(2, 4),
    ],
)
def test_load_from_pretrained_multi_agent(
    device, tmpdir, with_hp_config, observation_spaces, action_spaces
):
    # Initialize the dummy multi-agent
    agent_ids = ["agent1", "agent2"]

    hp_config = None
    if with_hp_config:
        hp_config = HyperparameterConfig(lr=RLParameter(min=0.05, max=0.2))
        agent = DummyMARLAlgorithm(
            observation_spaces,
            action_spaces,
            agent_ids=agent_ids,
            index=0,
            hp_config=hp_config,
        )
    else:
        agent = DummyMARLAlgorithm(
            observation_spaces, action_spaces, agent_ids=agent_ids, index=0
        )

    # Save the checkpoint to a file
    checkpoint_path = Path(tmpdir) / "checkpoint.pth"
    agent.save_checkpoint(checkpoint_path)

    # Create new agent object using the class method
    new_agent = DummyMARLAlgorithm.load(checkpoint_path, device=device)

    # Check if properties and weights are loaded correctly
    for i, agent_id in enumerate(agent_ids):
        assert (
            new_agent.observation_space[agent_id] == agent.observation_space[agent_id]
        )
        assert new_agent.action_space[agent_id] == agent.action_space[agent_id]

    for i in range(len(agent.dummy_actors)):
        assert isinstance(
            new_agent.dummy_actors[i], (EvolvableMLP, EvolvableCNN, EvolvableMultiInput)
        )
        assert str(new_agent.dummy_actors[i].to("cpu").state_dict()) == str(
            agent.dummy_actors[i].state_dict()
        )

    assert new_agent.lr == agent.lr
    assert new_agent.index == agent.index
    assert new_agent.scores == agent.scores
    assert new_agent.fitness == agent.fitness
    assert new_agent.steps == agent.steps
    assert new_agent.agent_ids == agent.agent_ids


@pytest.mark.parametrize(
    "observation_space",
    [
        generate_random_box_space((4,)),
    ],
)
def test_missing_attribute_warning(tmpdir, observation_space):
    action_space = generate_discrete_space(4)
    # Initialize the dummy agent
    agent = DummyRLAlgorithm(observation_space, action_space, index=0)

    # Save the checkpoint to a file
    checkpoint_path = Path(tmpdir) / "checkpoint.pth"
    agent.save_checkpoint(checkpoint_path)

    # Load and modify the checkpoint to remove an attribute
    checkpoint = torch.load(checkpoint_path, weights_only=False)
    checkpoint.pop("dummy_attribute")

    # Save the modified checkpoint
    modified_path = Path(tmpdir) / "modified_checkpoint.pth"
    torch.save(checkpoint, modified_path)

    # Load the modified checkpoint and check if a warning is raised
    with pytest.warns(
        UserWarning, match="Attribute dummy_attribute not found in checkpoint"
    ):
        new_agent = DummyRLAlgorithm.load(modified_path, device="cpu")

    # The attribute should keep its original value
    assert new_agent.dummy_attribute == "test_value"
