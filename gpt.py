import math
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten
from tokenizer import vocab_size, decode
from data import get_batch, block_size

n_embd = 128   # size of each character's "meaning" vector
n_head = 4     # attention heads per layer
n_layer = 4    # how many blocks we stack

class Attention(nn.Module):
    def __init__(self):
        super().__init__()
        self.query = nn.Linear(n_embd, n_embd, bias=False)
        self.key = nn.Linear(n_embd, n_embd, bias=False)
        self.value = nn.Linear(n_embd, n_embd, bias=False)
        self.proj = nn.Linear(n_embd, n_embd)

    def split_heads(self, t, B, T):
        return t.reshape(B, T, n_head, n_embd // n_head).transpose(0, 2, 1, 3)

    def __call__(self, x):
        B, T, C = x.shape
        q = self.split_heads(self.query(x), B, T)
        k = self.split_heads(self.key(x), B, T)
        v = self.split_heads(self.value(x), B, T)
        # how much each character cares about each other one
        scores = (q @ k.transpose(0, 1, 3, 2)) / math.sqrt(n_embd // n_head)
        # block the future: no peeking at the answer
        mask = mx.triu(mx.ones((T, T)), k=1) * -1e9
        weights = mx.softmax(scores + mask, axis=-1)
        out = (weights @ v).transpose(0, 2, 1, 3).reshape(B, T, C)
        return self.proj(out)

class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.norm1 = nn.LayerNorm(n_embd)
        self.attn = Attention()
        self.norm2 = nn.LayerNorm(n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(n_embd, 4 * n_embd), nn.GELU(), nn.Linear(4 * n_embd, n_embd)
        )

    def __call__(self, x):
        x = x + self.attn(self.norm1(x))   # gather info
        x = x + self.mlp(self.norm2(x))    # think about it
        return x

class GPT(nn.Module):
    def __init__(self):
        super().__init__()
        self.token_emb = nn.Embedding(vocab_size, n_embd)
        self.pos_emb = nn.Embedding(block_size, n_embd)
        self.blocks = [Block() for _ in range(n_layer)]
        self.norm = nn.LayerNorm(n_embd)
        self.out = nn.Linear(n_embd, vocab_size)

    def __call__(self, x):
        B, T = x.shape
        h = self.token_emb(x) + self.pos_emb(mx.arange(T))
        for block in self.blocks:
            h = block(h)
        return self.out(self.norm(h))

def loss_fn(model, x, y):
    return nn.losses.cross_entropy(model(x), y, reduction="mean")

def generate(model, n=500):
    ids = [0]
    for _ in range(n):
        context = mx.array([ids[-block_size:]])
        scores = model(context)[0, -1]
        ids.append(mx.random.categorical(scores).item())
    return decode(ids)

model = GPT()
n_params = sum(v.size for _, v in tree_flatten(model.parameters()))
print("parameters:", n_params)

optimizer = optim.AdamW(learning_rate=1e-3)
loss_and_grad = nn.value_and_grad(model, loss_fn)

for step in range(5000):
    x, y = get_batch("train")
    loss, grads = loss_and_grad(model, x, y)
    optimizer.update(model, grads)
    mx.eval(model.parameters(), optimizer.state)
    if step % 500 == 0:
        print("step", step, "loss", round(loss.item(), 3))

# final exam on text it never studied
val_loss = sum(loss_fn(model, *get_batch("val")).item() for _ in range(50)) / 50
print("val loss:", round(val_loss, 3))

model.save_weights("tinygpt.safetensors")
print("\n", generate(model))