import numpy as np
import pandas as pd

voltages = np.concatenate([
    np.arange(0, 21),
    np.arange(20,-21,-1),
    np.arange(-20,1)
])

df = pd.DataFrame({'Voltages':voltages})
df.to_csv('fast voltages.csv', index=False)
