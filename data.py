import mlx.core as mx
from tokenizer import text, encode

# the whole book as one long list of numbers
data = mx.array(encode(text))

# first 90% to learn from, last 10% to test on
n = int(0.9 * len(data))
train_data = data[:n]
val_data = data[n:]

block_size = 8   # how many characters the model sees at once
batch_size = 4   # how many examples it studies at a time

def get_batch(split):
    d = train_data if split == "train" else val_data
    # pick random starting spots in the text
    ix = mx.random.randint(0, len(d) - block_size, (batch_size,)).tolist()
    x = mx.stack([d[i : i + block_size] for i in ix])
    y = mx.stack([d[i + 1 : i + block_size + 1] for i in ix])
    return x, y

x, y = get_batch("train")
print("inputs:\n", x)
print("answers:\n", y)