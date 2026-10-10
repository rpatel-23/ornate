import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from tokenizer import vocab_size, decode
from data import get_batch

class BigramModel(nn.Module):
    def __init__(self):
        super().__init__()
        # a 65x65 table: for each character, a score for every possible next one
        self.table = nn.Embedding(vocab_size, vocab_size)

    def __call__(self, x):
        return self.table(x)

def loss_fn(model, x, y):
    scores = model(x)
    return nn.losses.cross_entropy(scores, y, reduction="mean")

def generate(model, n=300):
    ids = [0]
    for _ in range(n):
        scores = model(mx.array([ids[-1:]]))[0, -1]
        next_id = mx.random.categorical(scores).item()
        ids.append(next_id)
    return decode(ids)

model = BigramModel()
print("BEFORE training:\n", generate(model))

optimizer = optim.AdamW(learning_rate=1e-2)
loss_and_grad = nn.value_and_grad(model, loss_fn)

for step in range(3000):
    x, y = get_batch("train")
    loss, grads = loss_and_grad(model, x, y)
    optimizer.update(model, grads)
    mx.eval(model.parameters(), optimizer.state)
    if step % 500 == 0:
        print("step", step, "loss", round(loss.item(), 3))

print("\nAFTER training:\n", generate(model))