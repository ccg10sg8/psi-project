from parameters import sigma_max, number_of_hashes, output_bits, bin_capacity, alpha, hash_seeds, plain_modulus
from simple_hash import Simple_hash
from auxiliary_functions import coeffs_from_roots
from math import log2
import pickle
from oprf import server_prf_offline_parallel, order_of_generator, G
from time import time
from multiprocessing import freeze_support

#server's PRF secret key
oprf_server_key = 1234567891011121314151617181920


def main():
    print("Starting server offline")
    freeze_support()
    # key * generator of elliptic curve
    server_point_precomputed = (oprf_server_key % order_of_generator) * G

    server_set = []
    with open('server_set', 'r') as f:
        lines = f.readlines()
        print(lines)
    for item in lines:
        server_set.append(int(item.strip()))

    t0 = time()
    # The PRF function is applied on the set of the server, using parallel computation
    PRFed_server_set = server_prf_offline_parallel(server_set, server_point_precomputed)
    PRFed_server_set = set(PRFed_server_set)
    t1 = time()

    log_no_hashes = int(log2(number_of_hashes)) + 1
    dummy_msg_server = 2 ** (sigma_max - output_bits + log_no_hashes) + 1
    server_size = len(server_set)
    minibin_capacity = int(bin_capacity / alpha)
    number_of_bins = 2 ** output_bits

    # The OPRF-processed database entries are simple hashed
    SH = Simple_hash(hash_seeds)
    for item in PRFed_server_set:
        print(f"Processed {len(PRFed_server_set)} PRF items.")
        for i in range(number_of_hashes):
            SH.insert(item, i)

    # simple_hashed_data is padded with dummy_msg_server
    for i in range(number_of_bins):
        print(f"Hashing bin {i + 1}/{number_of_bins}")
        for j in range(bin_capacity):
            if SH.simple_hashed_data[i][j] is None:
                SH.simple_hashed_data[i][j] = dummy_msg_server

    # Partitioning:
    t2 = time()

    poly_coeffs = []
    for i in range(number_of_bins):
        coeffs_from_bin = []
        for j in range(alpha):
            roots = [SH.simple_hashed_data[i][minibin_capacity * j + r] for r in range(minibin_capacity)]
            coeffs_from_bin += coeffs_from_roots(roots, plain_modulus).tolist()
        poly_coeffs.append(coeffs_from_bin)

    with open('server_preprocessed', 'wb') as f:
        pickle.dump(poly_coeffs, f)

    t3 = time()
    print('Server OFFLINE time {:.2f}s'.format(t3 - t0))


if __name__ == '__main__':
    freeze_support()
    main()
