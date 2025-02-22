Deep Q-Learning (DQN)
=====================

DQN is an extension of Q-learning that makes use of a replay buffer and target network to improve learning stability.

* DQN paper: https://arxiv.org/abs/1312.5602

Can I use it?
------------

.. list-table::
   :widths: 20 20 20
   :header-rows: 1

   * - 
     - Action
     - Observation
   * - Discrete
     - ✔️
     - ✔️
   * - Continuous
     - ❌
     - ✔️

Example
------------

.. code-block:: python

  import gymnasium as gym
  from agilerl.utils import makeVectEnvs
  from agilerl.components.replay_buffer import ReplayBuffer
  from agilerl.algorithms.dqn import DQN

  # Create environment and Experience Replay Buffer
  env = makeVectEnvs('LunarLander-v2', num_envs=1)
  try:
      state_dim = env.single_observation_space.n          # Discrete observation space
      one_hot = True                                      # Requires one-hot encoding
  except:
      state_dim = env.single_observation_space.shape      # Continuous observation space
      one_hot = False                                     # Does not require one-hot encoding
  try:
      action_dim = env.single_action_space.n              # Discrete action space
  except:
      action_dim = env.single_action_space.shape[0]       # Continuous action space

  channels_last = False # Swap image channels dimension from last to first [H, W, C] -> [C, H, W]

  if channels_last:
      state_dim = (state_dim[2], state_dim[0], state_dim[1])

  field_names = ["state", "action", "reward", "next_state", "done"]
  memory = ReplayBuffer(action_dim=action_dim, memory_size=10000, field_names=field_names)

  agent = DQN(state_dim=state_dim, action_dim=action_dim, one_hot=one_hot)   # Create DQN agent

  state = env.reset()[0]  # Reset environment at start of episode
  while True:
      if channels_last:
          state = np.moveaxis(state, [3], [1])
      action = agent.getAction(state, epsilon)    # Get next action from agent
      next_state, reward, done, _, _ = env.step(action)   # Act in environment

      # Save experience to replay buffer
      if channels_last:
          memory.save2memoryVectEnvs(state, action, reward, np.moveaxis(next_state, [3], [1]), done)
      else:
          memory.save2memoryVectEnvs(state, action, reward, next_state, done)

      # Learn according to learning frequency
      if memory.counter % agent.learn_step == 0 and len(memory) >= agent.batch_size:
          experiences = memory.sample(agent.batch_size) # Sample replay buffer
          agent.learn(experiences)    # Learn according to agent's RL algorithm

To configure the network architecture, pass a dict to the DQN ``net_config`` field. For an MLP, this can be as simple as:

.. code-block:: python

  NET_CONFIG = {
        'arch': 'mlp',      # Network architecture
        'h_size': [32, 32]  # Network hidden size
    }

Or for a CNN:

.. code-block:: python

  NET_CONFIG = {
        'arch': 'cnn',      # Network architecture
        'h_size': [128],    # Network hidden size
        'c_size': [32, 32], # CNN channel size
        'k_size': [8, 4],   # CNN kernel size
        's_size': [4, 2],   # CNN stride size
        'normalize': True   # Normalize image from range [0,255] to [0,1]
    }

.. code-block:: python

  agent = DQN(state_dim=state_dim, action_dim=action_dim, one_hot=one_hot, net_config=NET_CONFIG)   # Create DQN agent  

Parameters
------------

.. autoclass:: agilerl.algorithms.dqn.DQN
  :members:
  :inherited-members:
