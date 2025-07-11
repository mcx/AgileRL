import math
from typing import Any, Callable, List, Union

import numpy as np
import torch
import torch.nn as nn


def map_pytree(f: Callable[[Union[np.ndarray, torch.Tensor]], Any], item: Any):
    """Apply a function to all tensors/arrays in a nested data structure.

    Recursively traverses nested dictionaries, lists, tuples, and sets,
    applying the given function to any numpy arrays or PyTorch tensors found.

    :param f: Function to apply to arrays/tensors
    :type f: Callable[[Union[np.ndarray, torch.Tensor]], Any]
    :param item: Nested data structure to traverse
    :type item: Any
    :return: Data structure with function applied to all arrays/tensors
    :rtype: Any
    """
    if isinstance(item, dict):
        return {k: map_pytree(f, v) for k, v in item.items()}
    elif isinstance(item, list) or isinstance(item, set) or isinstance(item, tuple):
        return [map_pytree(f, v) for v in item]
    elif isinstance(item, np.ndarray) or isinstance(item, torch.Tensor):
        return f(item)
    else:
        return item


def to(item: Any, device: torch.device):
    """Move all tensors/arrays in a nested data structure to specified device.

    :param item: Nested data structure containing tensors/arrays
    :type item: Any
    :param device: Target device to move tensors to
    :type device: torch.device
    :return: Data structure with tensors moved to device
    :rtype: Any
    """
    return map_pytree(lambda x: torch.tensor(x).to(device), item)


def to_decorator(f, device):
    """Decorator that moves the output of a function to a specified device.

    :param f: Function whose output should be moved to device
    :type f: Callable
    :param device: Target device
    :type device: torch.device
    :return: Decorated function
    :rtype: Callable
    """

    def new_f(*args, **kwargs):
        return to(f(*args, **kwargs), device)

    return new_f


def parameter_norm(model: nn.Module):
    """Calculate the L2 norm of all parameters in a model.

    :param model: PyTorch model
    :type model: nn.Module
    :return: L2 norm of all model parameters
    :rtype: float
    """
    norm = 0.0
    for param in model.parameters():
        norm += (param.norm() ** 2).item()
    return math.sqrt(norm)


def get_transformer_logs(
    attentions: List[torch.Tensor], model: nn.Module, attn_mask: torch.Tensor
):
    """Extract logging information from transformer attention weights.

    Computes attention entropy and parameter norm for transformer models,
    which can be useful for monitoring training dynamics.

    :param attentions: List of attention weight tensors from transformer layers
    :type attentions: List[torch.Tensor]
    :param model: Transformer model
    :type model: nn.Module
    :param attn_mask: Attention mask tensor
    :type attn_mask: torch.Tensor
    :return: Dictionary containing attention entropy and parameter norm
    :rtype: Dict[str, Tuple[float, int]]
    """
    logs = {}
    n = attn_mask.sum()
    model_attention_entropy = -sum(
        map(
            lambda x: ((x * torch.log(x + 1e-7)).sum(dim=-1) * attn_mask.unsqueeze(1))
            .sum()
            .item(),
            attentions,
        )
    ) / (len(attentions) * n)
    model_parameter_norm = parameter_norm(model)
    logs["attention_entropy"] = (model_attention_entropy, n * len(attentions))
    logs["parameter_norm"] = (model_parameter_norm, 1)
    return logs
