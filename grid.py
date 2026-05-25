import numpy as np
grid = np.zeros((1000,1000), dtype=int)
grid[500,500] = 1
print(f"Grid Shape: {grid.shape}")
print(f"Total Elements: {grid.size}")