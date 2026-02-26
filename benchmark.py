
import random
import time
from bubble_sort import bubble_sort

# Generate a list of 1000 random integers
random_list = [random.randint(0, 10000) for _ in range(1000)]

# Benchmark bubble_sort
sorted_copy = random_list.copy()
start_time = time.perf_counter()
bubble_sort(sorted_copy)
bubble_time = time.perf_counter() - start_time

# Benchmark Python's built-in sorted()
sorted_time = time.perf_counter()
sorted(random_list)
sorted_time = time.perf_counter() - sorted_time

# Print results
print(f"Bubble sort time: {bubble_time:.6f} seconds")
print(f"Built-in sorted() time: {sorted_time:.6f} seconds")
