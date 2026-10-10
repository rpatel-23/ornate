# load the text
with open("data/input.txt") as f:
    text = f.read()

print("characters:", len(text))
print(text[:200])

# every unique character is our vocabulary
chars = sorted(set(text))
vocab_size = len(chars)
print("vocab size:", vocab_size)

# translators: character <-> number
stoi = {ch: i for i, ch in enumerate(chars)}
itos = {i: ch for i, ch in enumerate(chars)}

def encode(s):
    return [stoi[c] for c in s]

def decode(ids):
    return "".join(itos[i] for i in ids)

print(encode("hello"))
print(decode(encode("hello")))