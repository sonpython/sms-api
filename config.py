def load_secret():
    with open("passkey.conf") as f:
        for line in f:
            if line.startswith("SECRET_KEY"):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("SECRET_KEY not found")
