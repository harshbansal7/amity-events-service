import bcrypt

def generate_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password_hash(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash) 