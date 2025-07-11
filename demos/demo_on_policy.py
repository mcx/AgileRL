from typing import List

import numpy as np
import torch
from tqdm import trange

from agilerl.algorithms import PPO
from agilerl.hpo.mutation import Mutations
from agilerl.hpo.tournament import TournamentSelection
from agilerl.utils.utils import create_population, make_vect_envs

# !Note: If you are running this demo without having installed agilerl,
# uncomment and place the following above agilerl imports:

# import sys
# sys.path.append('../')


if __name__ == "__main__":
    print("===== AgileRL On-policy Demo =====")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    NET_CONFIG = {
        "encoder_config": {
            "hidden_size": [32, 32],  # Actor hidden size
        }
    }

    INIT_HP = {
        "POP_SIZE": 6,  # Population size
        "BATCH_SIZE": 128,  # Batch size
        "LR": 1e-3,  # Learning rate
        "LEARN_STEP": 128,  # Learning frequency
        "GAMMA": 0.99,  # Discount factor
        "GAE_LAMBDA": 0.95,  # Lambda for general advantage estimation
        "ACTION_STD_INIT": 0.6,  # Initial action standard deviation
        "CLIP_COEF": 0.2,  # Surrogate clipping coefficient
        "ENT_COEF": 0.01,  # Entropy coefficient
        "VF_COEF": 0.5,  # Value function coefficient
        "MAX_GRAD_NORM": 0.5,  # Maximum norm for gradient clipping
        "TARGET_KL": None,  # Target KL divergence threshold
        "UPDATE_EPOCHS": 4,  # Number of policy update epochs
    }

    num_envs = 16
    env = make_vect_envs("LunarLander-v3", num_envs=num_envs)  # Create environment

    observation_space = env.single_observation_space
    action_space = env.single_action_space
    pop: List[PPO] = create_population(
        algo="PPO",  # Algorithm
        observation_space=observation_space,  # Observation space
        action_space=action_space,  # Action space
        net_config=NET_CONFIG,  # Network configuration
        INIT_HP=INIT_HP,  # Initial hyperparameters
        population_size=INIT_HP["POP_SIZE"],  # Population size
        num_envs=num_envs,  # Number of vectorized envs
        device=device,
    )

    tournament = TournamentSelection(
        tournament_size=2,  # Tournament selection size
        elitism=True,  # Elitism in tournament selection
        population_size=INIT_HP["POP_SIZE"],  # Population size
        eval_loop=1,  # Evaluate using last N fitness scores
    )

    mutations = Mutations(
        algo="PPO",  # Algorithm
        no_mutation=0.4,  # No mutation
        architecture=0.2,  # Architecture mutation
        new_layer_prob=0.2,  # New layer mutation
        parameters=0.2,  # Network parameters mutation
        activation=0,  # Activation layer mutation
        rl_hp=0.2,  # Learning HP mutation
        rl_hp_selection=["lr", "batch_size", "learn_step"],  # RL HPs to choose from
        mutation_sd=0.1,  # Mutation strength  # Network architecture
        rand_seed=1,  # Random seed
        device=device,
    )

    max_steps = 200000  # Max steps
    evo_steps = 10000  # Evolution frequency
    eval_steps = None  # Evaluation steps per episode - go until done
    eval_loop = 1  # Number of evaluation episodes

    total_steps = 0

    # TRAINING LOOP
    print("Training...")
    pbar = trange(max_steps, unit="step")
    while np.less([agent.steps[-1] for agent in pop], max_steps).all():
        pop_episode_scores = []
        for agent in pop:  # Loop through population
            obs, info = env.reset()  # Reset environment at start of episode
            scores = np.zeros(num_envs)
            completed_episode_scores = []
            steps = 0

            for _ in range(-(evo_steps // -agent.learn_step)):
                observations = []
                actions = []
                log_probs = []
                rewards = []
                dones = []
                values = []

                done = np.zeros(num_envs)

                learn_steps = 0

                for idx_step in range(-(agent.learn_step // -num_envs)):
                    # Get next action from agent
                    action, log_prob, _, value = agent.get_action(obs)

                    # Act in environment
                    next_obs, reward, terminated, truncated, info = env.step(action)
                    next_done = np.logical_or(terminated, truncated).astype(np.int8)

                    total_steps += num_envs
                    steps += num_envs
                    learn_steps += num_envs

                    observations.append(obs)
                    actions.append(action)
                    log_probs.append(log_prob)
                    rewards.append(reward)
                    dones.append(done)
                    values.append(value)

                    obs = next_obs
                    done = next_done
                    scores += np.array(reward)

                    for idx, (d, t) in enumerate(zip(terminated, truncated)):
                        if d or t:
                            completed_episode_scores.append(scores[idx])
                            agent.scores.append(scores[idx])
                            scores[idx] = 0

                pbar.update(learn_steps // len(pop))

                experiences = (
                    observations,
                    actions,
                    log_probs,
                    rewards,
                    dones,
                    values,
                    next_obs,
                    next_done,
                )
                # Learn according to agent's RL algorithm
                agent.learn(experiences)

            agent.steps[-1] += steps
            pop_episode_scores.append(completed_episode_scores)

        # Evaluate population
        fitnesses = [
            agent.test(
                env,
                max_steps=eval_steps,
                loop=eval_loop,
            )
            for agent in pop
        ]
        mean_scores = [
            (
                np.mean(episode_scores)
                if len(episode_scores) > 0
                else "0 completed episodes"
            )
            for episode_scores in pop_episode_scores
        ]

        print(f"--- Global steps {total_steps} ---")
        print(f"Steps {[agent.steps[-1] for agent in pop]}")
        print(f"Scores: {mean_scores}")
        print(f"Fitnesses: {['%.2f' % fitness for fitness in fitnesses]}")
        print(
            f"5 fitness avgs: {['%.2f' % np.mean(agent.fitness[-5:]) for agent in pop]}"
        )

        # Tournament selection and population mutation
        elite, pop = tournament.select(pop)
        pop = mutations.mutation(pop)

        # Update step counter
        for agent in pop:
            agent.steps.append(agent.steps[-1])

    pbar.close()
    env.close()
