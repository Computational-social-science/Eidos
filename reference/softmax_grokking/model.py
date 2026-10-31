"""Declared paper-aligned Transformer; unspecified paper details live in protocol.json."""
import math
import torch
from torch import nn


class Transformer(nn.Module):
    def __init__(self, modulus=31, width=64, heads=4):
        super().__init__()
        self.position = nn.Parameter(torch.randn(2, width) * .02)
        self.embedding = nn.Embedding(modulus, width)
        self.qkv = nn.Linear(width, 3 * width)
        self.projection = nn.Linear(width, width)
        self.ff1 = nn.Linear(width, 4 * width)
        self.ff2 = nn.Linear(4 * width, width)
        self.head = nn.Linear(width, modulus)
        self.heads = heads

    def forward(self, tokens):
        x = self.embedding(tokens) + self.position
        batch, length, width = x.shape
        q, k, v = [part.reshape(batch, length, self.heads, width // self.heads).transpose(1, 2)
                   for part in self.qkv(x).chunk(3, dim=-1)]
        scores = (q @ k.transpose(-2, -1)) / math.sqrt(width // self.heads)
        mask = torch.ones(length, length, device=x.device, dtype=torch.bool).triu(1)
        attention = scores.masked_fill(mask, -torch.inf).softmax(dim=-1) @ v
        x = x + self.projection(attention.transpose(1, 2).reshape(batch, length, width))
        x = x + self.ff2(self.ff1(x).relu())
        return self.head(x[:, -1])
