import subprocess

def get_ollama_models():
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    else:
        raise RuntimeError(f"Ошибка: {result.stderr}")
print(get_ollama_models())