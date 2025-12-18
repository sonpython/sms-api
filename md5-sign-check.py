import hashlib

# Đọc key từ file passkey.conf
# File chỉ chứa đúng 1 dòng: SECRET_KEY=xxxx hoặc chỉ giá trị key
def load_key(path="passkey.conf"):
    with open(path, "r", encoding="utf-8") as f:
        line = f.read().strip()
        if "=" in line:
            return line.split("=", 1)[1].strip()
        return line

sdt = "0969999290"
msg = "Hello from API"
key = load_key("/opt/sms-api/passkey.conf")

raw = f"{sdt}&{msg}&{key}"
md5_hash = hashlib.md5(raw.encode("utf-8")).hexdigest()

print(md5_hash)
