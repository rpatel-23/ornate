def read_file(path):
    with open(path) as f:
        text = f.read()
    return text