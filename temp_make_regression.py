#!/usr/bin/env python
# coding: utf-8

# **トイデータ生成**
#  - https://qiita.com/fujin/items/bb82d77b0b08c107f819
#  - https://sabopy.com/py/scikit-learn-8/

# In[1]:


import numpy as np
import pandas as pd
import os
from sklearn.datasets import make_regression

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)

# 実行上問題ないwarningは非表示にする
import warnings
warnings.filterwarnings('ignore')

# データ生成
# n_informative : 線形モデルに適合するデータ（列）の数を設定できる
# n_targets : 目的変数の数
# noise : ばらつきを付与できる
# ランダムな値を生成するため random_state は固定しない

n_features = 10
X_raw, y_raw = make_regression(n_samples=1000, n_features=n_features, n_informative=int(n_features/2), n_targets=1, noise=80)
X_raw = X_raw * 100

# pandas.DataFrame 形式に変換
columns = [f'f{i+1}' for i in range(n_features)]
df = pd.DataFrame(X_raw, columns=columns)
df['y'] = y_raw


# **ランダムにデータを30%欠損させ保存する**

# In[2]:


size = int(len(df) * 0.3)

# ランダムに欠損させる
for k in df.keys():
    # 欠損させるのは特徴量**ランダムにデータを30%欠損させ、欠損ありのCSVを保存する**のみ
    if k != 'y':
        rand = np.random.randint(0, len(df) , size = size)
        df.loc[rand,k] = np.nan


# In[3]:

print(os.getcwd())
print(df)

df.to_csv('out.csv')