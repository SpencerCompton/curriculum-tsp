"""Defines the main task for the TSP

The TSP is defined by the following traits:
    1. Each city in the list must be visited once and only once
    2. The salesman must return to the original node at the end of the tour

Since the TSP doesn't have dynamic elements, we return an empty list on
__getitem__, which gets processed in trainer.py to be None

"""

import os
import numpy as np
import torch
import matplotlib
import matplotlib.pyplot as plt

from torch.utils.data import Dataset

from . import node_distrib
from .node_distrib import get_param_nodes

matplotlib.use("Agg")

class _TSPStage:
    """Stage of curriculum for training on tsp task.
    
    This is a helper object to keep track of a few things.

    Attributes:
        num_tiles (int): number of tiles in this stage
        param (torch.Tensor): parameter describing the data distribution
        start (int): the epoch number at which this stage activates
        length (int): the number of epochs this stage runs for
    """
    def __init__(self, num_tiles, param, start, length):
        """Create TSPStage instance.

        Args:
            num_tiles (int): number of tiles in this stage
            param (torch.Tensor): parameter describing the data distribution
            start (int): the epoch number at which this stage activates
            length (int): the number of epochs this stage runs for
        """
        self.num_tiles = num_tiles
        self.param = param
        self.start = start
        self.length = length


class TSPCurriculum:
    """Curriculum for training on tsp task."""
    def __init__(self, num_nodes, num_samples, seed):
        """Create TSP curriculum.

        Args:
            num_nodes (int): number of nodes per problem instance
            num_samples (int): number of problem instances in dataset
            seed (int): random seed
        """
        self._num_nodes = num_nodes
        self._num_samples = num_samples
        self._seed = seed

        self._stages = list()

        self._curr_stage_index = None
        self._curr_stage = None
        self._curr_dataset = None

        self._curr_epoch = -1
        self._curr_len = 0

        self._finished = False # need to figure out how to finish up


    def increment_epoch(self):
        """Increment the current epoch of the curriculum.
        
        Indicates that we have trained for an epoch.
        """
        self._curr_epoch += 1

        if self._curr_epoch == self._curr_len:
            # can't increment anymore
            self._finished = True

        new_stage_epoch = self._curr_stage.start + self._curr_stage.length + 1
        if self._curr_epoch == new_stage_epoch and not self._finished:
            # load new stage and new dataset
            self._curr_stage_index += 1
            self._curr_stage = self._stages[self._curr_stage_index]
            self._curr_dataset = TSPDataset(
                num_nodes=self._num_nodes,
                num_samples=self._num_samples,
                seed=self._seed,
                num_tiles=self._curr_stage.num_tiles,
                param=self._curr_stage.param
            )

    def get_dataset(self):
        """Get the dataset of the current epoch."""
        assert not self._finished
        return self._curr_dataset

    def add_stage(self, num_tiles, param, num_epochs):
        """Add a stage to the curriculum.

        Args
            num_tiles (int): number of tiles
            param (torch.Tensor): parameter for distribution of nodes
            num_epochs (int): number of epochs to train on this distribution
        """
        curr_stage = _TSPStage(num_tiles, param, self._curr_len, num_epochs)
        self._stages.append(curr_stage)
        self._curr_len += num_epochs
    
    def start(self):
        """Start up the curriculum after adding all stages."""
        self._curr_epoch = 0
        self._curr_stage_index = 0
        self._curr_stage = self._stages[self._curr_stage_index]
        self._curr_dataset = TSPDataset(
            num_nodes=self._num_nodes,
            num_samples=self._num_samples,
            seed=self._seed,
            num_tiles=self._curr_stage.num_tiles,
            param=self._curr_stage.param
        )


class TSPDataset(Dataset):
    def __init__(
        self, num_nodes=50, num_samples=1e6, seed=None, num_tiles=None, param=None
    ):
        """Create TSP dataset.

        Args:
            num_nodes (int): number of nodes per problem instance
            num_samples (int): number of problem instances in dataset
            seed (int): random seed
            param (torch.Tensor): parameter for distribution of nodes
        """
        super(TSPDataset, self).__init__()

        if seed is None:
            seed = np.random.randint(123456789)

        np.random.seed(seed)
        torch.manual_seed(seed)
        self.dataset = get_param_nodes(num_nodes, num_samples, seed, num_tiles, param)
        self.dynamic = torch.zeros(num_samples, 1, num_nodes)
        self.num_nodes = num_nodes
        self.size = num_samples

    def __len__(self):
        return self.size

    def __getitem__(self, idx):
        # (static, dynamic, start_loc)
        return (self.dataset[idx], self.dynamic[idx], [])



# tsp has no update mask function (it points to None)

def update_mask(mask, dynamic, chosen_idx):
    """Marks the visited city, so it can't be selected a second time."""
    mask.scatter_(1, chosen_idx.unsqueeze(1), 0)
    return mask


def reward(static, tour_indices):
    """
    Parameters
    ----------
    static: torch.FloatTensor containing static (e.g. x, y) data
    tour_indices: torch.IntTensor of size (batch_size, num_cities)

    Returns
    -------
    Euclidean distance between consecutive nodes on the route. of size
    (batch_size, num_cities)
    """

    # Convert the indices back into a tour
    idx = tour_indices.unsqueeze(1).expand_as(static)
    tour = torch.gather(static.data, 2, idx).permute(0, 2, 1)

    # Make a full tour by returning to the start
    y = torch.cat((tour, tour[:, :1]), dim=1)

    # Euclidean distance between each consecutive point
    tour_len = torch.sqrt(torch.sum(torch.pow(y[:, :-1] - y[:, 1:], 2), dim=2))

    return tour_len.sum(1).detach()


def render(static, tour_indices, save_path):
    """Plots the found tours."""

    plt.close("all")

    num_plots = 3 if int(np.sqrt(len(tour_indices))) >= 3 else 1

    _, axes = plt.subplots(nrows=num_plots, ncols=num_plots, sharex="col", sharey="row")

    if num_plots == 1:
        axes = [[axes]]
    axes = [a for ax in axes for a in ax]

    for i, ax in enumerate(axes):

        # Convert the indices back into a tour
        idx = tour_indices[i]
        if len(idx.size()) == 1:
            idx = idx.unsqueeze(0)

        # End tour at the starting index
        idx = idx.expand(static.size(1), -1)
        idx = torch.cat((idx, idx[:, 0:1]), dim=1)

        data = torch.gather(static[i].data, 1, idx).cpu().numpy()

        # plt.subplot(num_plots, num_plots, i + 1)
        ax.plot(data[0], data[1], zorder=1)
        ax.scatter(data[0], data[1], s=4, c="r", zorder=2)
        ax.scatter(data[0, 0], data[1, 0], s=20, c="k", marker="*", zorder=3)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=400)