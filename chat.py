from mlx_lm import load, generate

model, tokenizer = load("mlx-community/Qwen3-8B-4bit")

# the running conversation, starting with who the model is
messages = [{"role": "system", "content": "You are Ornate, a helpful assistant."}]

while True:
    user = input("\nyou: ")
    if user.strip().lower() in ("q", "quit"):
        break
    messages.append({"role": "user", "content": user})

    # turn the whole conversation into the format the model expects
    prompt = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, enable_thinking=False
    )
    reply = generate(model, tokenizer, prompt=prompt, max_tokens=2000)

    print("\nornate:", reply)
    messages.append({"role": "assistant", "content": reply})