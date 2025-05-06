import socket
import tenseal as ts
import pickle
import numpy as np
from math import log2
from time import time

from parameters import number_of_hashes, bin_capacity, alpha, ell
from auxiliary_functions import power_reconstruct
from oprf import server_prf_online_parallel

oprf_server_key = 1234567891011121314151617181920

def main():
    log_no_hashes = int(log2(number_of_hashes)) + 1
    base = 2 ** ell
    minibin_capacity = int(bin_capacity / alpha)
    logB_ell = int(log2(minibin_capacity) / ell) + 1

    print("[SERVER] Loading server preprocessed data...")
    with open('server_preprocessed', 'rb') as g:
        poly_coeffs = pickle.load(g)

    transposed_poly_coeffs = np.transpose(poly_coeffs).tolist()

    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serv.bind(('localhost', 4471))
    serv.listen(1)
    print("[SERVER] Listening on localhost:4471")

    for i in range(1):
        print("[SERVER] Waiting for client connection...")
        conn, addr = serv.accept()
        print(f"[SERVER] Client connected from {addr}")

        L = conn.recv(10).decode().strip()
        L = int(L, 10)
        print(f"[SERVER] Expecting {L} bytes of encoded client set")

        encoded_client_set_serialized = b""
        while len(encoded_client_set_serialized) < L:
            data = conn.recv(4096)
            if not data:
                break
            encoded_client_set_serialized += data
        encoded_client_set = pickle.loads(encoded_client_set_serialized)
        print("[SERVER] Encoded client set received and deserialized")

        t0 = time()
        PRFed_encoded_client_set = server_prf_online_parallel(oprf_server_key, encoded_client_set)
        PRFed_encoded_client_set_serialized = pickle.dumps(PRFed_encoded_client_set, protocol=None)
        L = len(PRFed_encoded_client_set_serialized)
        sL = str(L) + ' ' * (10 - len(str(L)))

        conn.sendall((sL).encode())
        conn.sendall(PRFed_encoded_client_set_serialized)
        print(" * OPRF layer done!")
        t1 = time()

        L = conn.recv(10).decode().strip()
        L = int(L, 10)
        print(f"[SERVER] Expecting {L} bytes of encrypted HE query and context")

        final_data = b""
        while len(final_data) < L:
            data = conn.recv(4096)
            if not data:
                break
            final_data += data

        t2 = time()
        received_data = pickle.loads(final_data)
        srv_context = ts.context_from(received_data[0])
        received_enc_query_serialized = received_data[1]

        received_enc_query = [[None for j in range(logB_ell)] for i in range(base - 1)]
        for i in range(base - 1):
            for j in range(logB_ell):
                if (i + 1) * base ** j - 1 < minibin_capacity:
                    received_enc_query[i][j] = ts.bfv_vector_from(
                        srv_context, received_enc_query_serialized[i][j])

        all_powers = [None for _ in range(minibin_capacity)]
        for i in range(base - 1):
            for j in range(logB_ell):
                if (i + 1) * base ** j - 1 < minibin_capacity:
                    all_powers[(i + 1) * base ** j - 1] = received_enc_query[i][j]

        for k in range(minibin_capacity):
            if all_powers[k] is None:
                all_powers[k] = power_reconstruct(received_enc_query, k + 1)
        all_powers = all_powers[::-1]
        print("[SERVER] Reconstructed all encrypted powers")

        srv_answer = []
        for i in range(alpha):
            dot_product = all_powers[0]
            for j in range(1, minibin_capacity):
                dot_product = dot_product + transposed_poly_coeffs[
                    (minibin_capacity + 1) * i + j] * all_powers[j]
            dot_product = dot_product + transposed_poly_coeffs[
                (minibin_capacity + 1) * i + minibin_capacity]
            srv_answer.append(dot_product.serialize())

        response_to_be_sent = pickle.dumps(srv_answer, protocol=None)
        t3 = time()
        L = len(response_to_be_sent)
        sL = str(L) + ' ' * (10 - len(str(L)))

        conn.sendall((sL).encode())
        conn.sendall(response_to_be_sent)

        print("[SERVER] Response sent to client.")
        print("Client disconnected \n")
        print("Server ONLINE computation time {:.2f}s".format(t1 - t0 + t3 - t2))
        conn.close()

if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()
