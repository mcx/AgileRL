import gymnasium as gym
import numpy as np
import matplotlib.pyplot as plt
from agilerl.algorithms.cqn import CQN
from agilerl.algorithms.dqn import DQN
from agilerl.algorithms.ddpg import DDPG
from agilerl.algorithms.td3 import TD3
from agilerl.algorithms.maddpg import MADDPG
from agilerl.algorithms.matd3 import MATD3


def makeVectEnvs(env_name, num_envs=1):
    """Returns async-vectorized gym environments.

    :param env_name: Gym environment name
    :type env_name: str
    :param num_envs: Number of vectorized environments, defaults to 1
    :type num_envs: int, optional
    """
    return gym.vector.AsyncVectorEnv(
        [lambda: gym.make(env_name) for i in range(num_envs)])


def initialPopulation(algo, state_dim, action_dim, one_hot,
                      net_config, INIT_HP, population_size=1, device='cpu', 
                      accelerator=None):
    """Returns population of identical agents.

    :param algo: RL algorithm
    :type algo: str
    :param state_dim: State observation dimension
    :type state_dim: int
    :param action_dim: Action dimension
    :type action_dim: int
    :param one_hot: One-hot encoding
    :type one_hot: bool
    :param INIT_HP: Initial hyperparameters
    :type INIT_HP: dict
    :param population_size: Number of agents in population, defaults to 1
    :type population_size: int, optional
    :param device: Device for accelerated computing, 'cpu' or 'cuda', defaults to 'cpu'
    :type device: str, optional
    :param accelerator: Accelerator for distributed computing, defaults to None
    :type accelerator: Hugging Face accelerate.Accelerator(), optional
    """
    population = []

    if algo == 'DQN':
        for idx in range(population_size):
            agent = DQN(
                state_dim=state_dim,
                action_dim=action_dim,
                one_hot=one_hot,
                index=idx,
                net_config=net_config,
                batch_size=INIT_HP['BATCH_SIZE'],
                lr=INIT_HP['LR'],
                learn_step=INIT_HP['LEARN_STEP'],
                gamma=INIT_HP['GAMMA'],
                tau=INIT_HP['TAU'],
                double=INIT_HP['DOUBLE'],
                device=device,
                accelerator=accelerator
            )
            population.append(agent)

    elif algo == 'DDPG':
        for idx in range(population_size):
            agent = DDPG(
                state_dim=state_dim,
                action_dim=action_dim,
                one_hot=one_hot,
                index=idx,
                net_config=net_config,
                batch_size=INIT_HP['BATCH_SIZE'],
                lr=INIT_HP['LR'],
                learn_step=INIT_HP['LEARN_STEP'],
                gamma=INIT_HP['GAMMA'],
                tau=INIT_HP['TAU'],
                policy_freq=INIT_HP['POLICY_FREQ'],
                device=device,
                accelerator=accelerator
            )
            population.append(agent)

    elif algo == 'CQN':
        for idx in range(population_size):
            agent = CQN(
                state_dim=state_dim,
                action_dim=action_dim,
                one_hot=one_hot,
                index=idx,
                net_config=net_config,
                batch_size=INIT_HP['BATCH_SIZE'],
                lr=INIT_HP['LR'],
                learn_step=INIT_HP['LEARN_STEP'],
                gamma=INIT_HP['GAMMA'],
                tau=INIT_HP['TAU'],
                double=INIT_HP['DOUBLE'],
                device=device,
                accelerator=accelerator
            )
            population.append(agent)

    elif algo == 'TD3':
        for idx in range(population_size):
            agent = TD3(
                state_dim=state_dim,
                action_dim=action_dim,
                one_hot=one_hot,
                max_action=INIT_HP['MAX_ACTION'],
                index=idx,
                net_config=net_config,
                batch_size=INIT_HP['BATCH_SIZE'],
                lr=INIT_HP['LR'],
                learn_step=INIT_HP['LEARN_STEP'],
                gamma=INIT_HP['GAMMA'],
                tau=INIT_HP['TAU'],
                policy_freq=INIT_HP['POLICY_FREQ'],
                device=device,
                accelerator=accelerator
            )
            population.append(agent)

    elif algo == 'MADDPG':
        for idx in range(population_size):
            agent = MADDPG(
                state_dims=state_dim,
                action_dims=action_dim,
                one_hot=one_hot,
                n_agents=INIT_HP['N_AGENTS'],
                agent_ids=INIT_HP['AGENT_IDS'],
                index=idx,
                max_action = INIT_HP['MAX_ACTION'],
                min_action = INIT_HP['MIN_ACTION'],
                net_config=net_config,
                batch_size=INIT_HP['BATCH_SIZE'],
                lr=INIT_HP['LR'],
                learn_step=INIT_HP['LEARN_STEP'],
                gamma=INIT_HP['GAMMA'],
                tau=INIT_HP['TAU'],
                discrete_actions=INIT_HP['DISCRETE_ACTIONS'],
                device=device,
                accelerator=accelerator,
            )
            population.append(agent)

    elif algo == 'MATD3':
        for idx in range(population_size):
            agent = MATD3(
                state_dims=state_dim,
                action_dims=action_dim,
                one_hot=one_hot,
                n_agents=INIT_HP['N_AGENTS'],
                agent_ids=INIT_HP['AGENT_IDS'],
                index=idx,
                max_action = INIT_HP['MAX_ACTION'],
                min_action = INIT_HP['MIN_ACTION'],
                net_config=net_config,
                batch_size=INIT_HP['BATCH_SIZE'],
                lr=INIT_HP['LR'],
                policy_freq=INIT_HP['POLICY_FREQ'],
                learn_step=INIT_HP['LEARN_STEP'],
                gamma=INIT_HP['GAMMA'],
                tau=INIT_HP['TAU'],
                discrete_actions=INIT_HP['DISCRETE_ACTIONS'],
                device=device,
                accelerator=accelerator,
            )
            population.append(agent)


    return population


def printHyperparams(pop):
    """Prints current hyperparameters of agents in a population and their fitnesses.

    :param pop: Population of agents
    :type pop: List[object]
    """
    
    for agent in pop:
        print('Agent ID: {}    Mean 100 fitness: {:.2f}    lr: {}    Batch Size: {}'.format(
            agent.index, np.mean(agent.fitness[-100:]), agent.lr, agent.batch_size))


def plotPopulationScore(pop):
    """Plots the fitness scores of agents in a population.

    :param pop: Population of agents
    :type pop: List[object]
    """
    plt.figure()
    for agent in pop:
        scores = agent.fitness
        steps = agent.steps[:-1]
        plt.plot(steps, scores)
    plt.title("Score History - Mutations")
    plt.xlabel("Steps")
    plt.ylim(bottom=-400)
    plt.show()
