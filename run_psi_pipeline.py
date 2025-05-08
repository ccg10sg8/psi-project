import subprocess
import time
import re
import os
import sys

# === 1. Prompt for sizes ===
client_size = int(input("Enter CLIENT set size: "))
server_size = int(input("Enter SERVER set size: "))
intersection_size = int(input("Enter INTERSECTION size: "))

# === 2. Modify parameters.py ===
param_path = "parameters.py"

with open(param_path, "r") as f:
    lines = f.readlines()

def replace_param(line, name, value):
    return re.sub(rf"^{name}\s*=.*", f"{name} = {value}", line)

updated_lines = []
for line in lines:
    if line.strip().startswith("client_size"):
        updated_lines.append(replace_param(line, "client_size", client_size))
    elif line.strip().startswith("server_size"):
        updated_lines.append(replace_param(line, "server_size", server_size))
    elif line.strip().startswith("intersection_size"):
        updated_lines.append(replace_param(line, "intersection_size", intersection_size))
    else:
        updated_lines.append(line)

with open(param_path, "w") as f:
    f.writelines(updated_lines)
    f.flush()
    os.fsync(f.fileno())  # Ensure the file is written to disk

time.sleep(0.5)  # Give filesystem a moment to sync
print("parameters.py updated.")

# === 3. Use the correct interpreter ===
python_exec = sys.executable

# === 4. Run set_gen.py ===
print("\nGenerating sets...")
subprocess.run([python_exec, "set_gen.py"], check=True)

# === 5. Run server_offline.py and client_offline.py ===
print("\nRunning server_offline.py...")
subprocess.run([python_exec, "server_offline.py"], check=True)

print("\nRunning client_offline.py...")
subprocess.run([python_exec, "client_offline.py"], check=True)

# === 6. Start server_online.py in background ===
print("\nStarting server_online.py...")
server_proc = subprocess.Popen([python_exec, "server_online.py"])
time.sleep(2)  # Wait for server to be ready

# === 7. Run client_online.py ===
print("\nRunning client_online.py...")
subprocess.run([python_exec, "client_online.py"], check=True)

# === 8. Shutdown server ===
print("\nPSI protocol complete. Terminating server process...")
server_proc.terminate()

# === 9. Write metadata log ===
with open("run_metadata.txt", "w") as f:
    f.write(f"Client set size: {client_size}\n")
    f.write(f"Server set size: {server_size}\n")
    f.write(f"Intersection size: {intersection_size}\n")
    f.write(f"Run completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

print("Metadata saved to run_metadata.txt")

# === 10. Verify correctness of intersection ===
try:
    with open("client_intersection_result.txt") as f:
        client_result = sorted(int(line.strip()) for line in f if line.strip().isdigit())

    with open("intersection") as f:
        true_intersection = sorted(int(line.strip()) for line in f if not line.startswith("#"))

    if client_result == true_intersection:
        print("Intersection verification passed: client result matches true intersection.")
    else:
        print("Intersection verification failed: mismatch detected.")
        print(f" - Client result size: {len(client_result)}")
        print(f" - True intersection size: {len(true_intersection)}")
        missing = set(true_intersection) - set(client_result)
        extra = set(client_result) - set(true_intersection)
        if missing:
            print(f" - Missing elements: {sorted(missing)}")
        if extra:
            print(f" - Extra elements: {sorted(extra)}")
except FileNotFoundError:
    print("Could not verify intersection: result files missing.")
