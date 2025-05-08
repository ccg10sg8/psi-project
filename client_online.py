import tenseal as ts
from time import time
import socket
import pickle
from math import log2
from parameters import sigma_max, output_bits, plain_modulus, poly_modulus_degree, number_of_hashes, bin_capacity, alpha, ell, hash_seeds
from cuckoo_hash import reconstruct_item, Cuckoo
from auxiliary_functions import windowing
from oprf import order_of_generator, client_prf_online_parallel

LOG_TO_FILE = True

def log(msg):
    print(msg)
    if LOG_TO_FILE:
        with open("client_log.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def main():
    oprf_client_key = 12345678910111213141516171819222222222222

    log_no_hashes = int(log2(number_of_hashes)) + 1
    base = 2 ** ell
    minibin_capacity = int(bin_capacity / alpha)
    logB_ell = int(log2(minibin_capacity) / ell) + 1
    dummy_msg_client = 2 ** (sigma_max - output_bits + log_no_hashes)

    log("[CLIENT] Connecting to server...")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('localhost', 4471))

    log("[CLIENT] Setting up HE context...")
    private_context = ts.context(ts.SCHEME_TYPE.BFV, poly_modulus_degree=poly_modulus_degree, plain_modulus=plain_modulus)
    public_context = ts.context_from(private_context.serialize())
    public_context.make_context_public()

    log("[CLIENT] Loading preprocessed client set...")
    with open("client_preprocessed", "rb") as f:
        encoded_client_set = pickle.load(f)
    encoded_client_set_serialized = pickle.dumps(encoded_client_set, protocol=None)

    L = len(encoded_client_set_serialized)
    sL = str(L) + ' ' * (10 - len(str(L)))
    client.sendall(sL.encode())
    client.sendall(encoded_client_set_serialized)
    log(f"[CLIENT] Sent {L} bytes of encoded client set")

    L = client.recv(10).decode().strip()
    L = int(L, 10)
    log(f"[CLIENT] Expecting {L} bytes of PRFed data from server")

    PRFed_encoded_client_set_serialized = b""
    while len(PRFed_encoded_client_set_serialized) < L:
        data = client.recv(4096)
        if not data:
            break
        PRFed_encoded_client_set_serialized += data
    PRFed_encoded_client_set = pickle.loads(PRFed_encoded_client_set_serialized)

    log("[CLIENT] Finalizing OPRF with inverse key")
    t0 = time()
    key_inverse = pow(oprf_client_key, -1, order_of_generator)
    PRFed_client_set = client_prf_online_parallel(key_inverse, PRFed_encoded_client_set)
    log("[CLIENT] OPRF protocol complete")

    log("[CLIENT] Inserting into Cuckoo hashing structure")
    CH = Cuckoo(hash_seeds)
    for item in PRFed_client_set:
        CH.insert(item)
    for i in range(CH.number_of_bins):
        if CH.data_structure[i] is None:
            CH.data_structure[i] = dummy_msg_client

    log("[CLIENT] Applying windowing and encrypting query...")
    windowed_items = [windowing(item, minibin_capacity, plain_modulus) for item in CH.data_structure]

    plain_query = [None for _ in range(len(windowed_items))]
    enc_query = [[None for _ in range(logB_ell)] for _ in range(1, base)]
    for j in range(logB_ell):
        for i in range(base - 1):
            if (i + 1) * base ** j - 1 < minibin_capacity:
                for k in range(len(windowed_items)):
                    plain_query[k] = windowed_items[k][i][j]
                enc_query[i][j] = ts.bfv_vector(private_context, plain_query)

    enc_query_serialized = [[None for _ in range(logB_ell)] for _ in range(1, base)]
    for j in range(logB_ell):
        for i in range(base - 1):
            if (i + 1) * base ** j - 1 < minibin_capacity:
                enc_query_serialized[i][j] = enc_query[i][j].serialize()

    context_serialized = public_context.serialize()
    message_to_be_sent = [context_serialized, enc_query_serialized]
    message_to_be_sent_serialized = pickle.dumps(message_to_be_sent, protocol=None)
    t1 = time()

    L = len(message_to_be_sent_serialized)
    sL = str(L) + ' ' * (10 - len(str(L)))
    client.sendall(sL.encode())
    client.sendall(message_to_be_sent_serialized)
    log("[CLIENT] Sent encrypted query and context to server")

    log("[CLIENT] Waiting for server's response...")
    L = client.recv(10).decode().strip()
    L = int(L, 10)
    answer = b""
    while len(answer) < L:
        data = client.recv(4096)
        if not data:
            break
        answer += data

    t2 = time()
    ciphertexts = pickle.loads(answer)
    decryptions = [ts.bfv_vector_from(private_context, ct).decrypt() for ct in ciphertexts]
    log("[CLIENT] Decryption complete. Recovering intersection...")

    recover_CH_structure = [matrix[0][0] for matrix in windowed_items]
    count = [0] * alpha

    with open('client_set', 'r') as g:
        client_set_entries = g.readlines()
    client_intersection = []

    for j in range(alpha):
        for i in range(poly_modulus_degree):
            if decryptions[j][i] == 0:
                count[j] += 1
                PRFed_common_element = reconstruct_item(recover_CH_structure[i], i, hash_seeds[recover_CH_structure[i] % (2 ** log_no_hashes)])
                index = PRFed_client_set.index(PRFed_common_element)
                client_intersection.append(int(client_set_entries[index].strip()))

    with open('intersection', 'r') as h:
        real_intersection = [int(line.strip()) for line in h]

    t3 = time()
    match = set(client_intersection) == set(real_intersection)
    log(f"[CLIENT] Intersection recovered correctly: {match}")
    log(f"[CLIENT] Intersection size: {len(client_intersection)}")
    log(f"[CLIENT] Contents: {sorted(client_intersection)}")

    # Save result
    with open('client_intersection_result.txt', 'w') as f:
        for item in sorted(client_intersection):
            f.write(f"{item}\n")

    log("[CLIENT] Intersection written to client_intersection_result.txt")
    log(f"[CLIENT] Client ONLINE computation time: {t1 - t0 + t3 - t2:.2f}s")
    log("[CLIENT] Disconnecting...")
    client.close()


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()
