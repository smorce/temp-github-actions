#!/usr/bin/env python
# coding: utf-8

# **トイデータ生成**
#  - https://qiita.com/fujin/items/bb82d77b0b08c107f819
#  - https://sabopy.com/py/scikit-learn-8/

# In[1]:


import numpy as np
import pandas as pd
from sklearn.datasets import make_regression
import random
import datetime

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

# 特徴量数
n_features = 10
# 通常のノイズ設定
noise = 10
# N 回ごとに大きい noise を発生させる
N = 3
if random.randint(1, N) // N != 1:
    # 通常のフロー
    print("今回の設定ノイズを表示します(設定値 10 or 200) :", noise)
else:
    # N 回に 1 回の割合で 200 のノイズ設定になる
    noise = 200
    print("今回の設定ノイズを表示します(設定値 10 or 200) :", noise)

X_raw, y_raw = make_regression(n_samples=1000, n_features=n_features, n_informative=int(n_features/2), n_targets=1, noise=noise)
# X の値が小さいので100倍する
X_raw = X_raw * 100


# pandas.DataFrame 形式に変換
columns = [f'f{i+1}' for i in range(n_features)]
df = pd.DataFrame(X_raw, columns=columns)
df['y'] = y_raw
df['noise'] = noise
# str 型で時間を記録(例：'_2022_0505_0324_46')
now = datetime.datetime.now()
time = now.strftime("_%Y_%m%d_%H%M_%S")
df['time'] = time



# **ランダムにデータを30%欠損させ保存する**

# In[2]:


size = int(len(df) * 0.3)

# ランダムに欠損させる
for k in df.keys():
    # 欠損させるのは特徴量
    # ランダムにデータを30%欠損させ、欠損ありのCSVを保存するのみ
    if k not in ['y', 'noise', 'time']:
        rand = np.random.randint(0, len(df) , size = size)
        df.loc[rand,k] = np.nan


# In[3]:


df.to_csv('./data/df.csv', index=False)


# **作成した欠損データを GCS にアップロードする**

# In[4]:


# **CloudStorageに接続**

# In[6]:

from google.cloud import storage
client = storage.Client()
# https://console.cloud.google.com/storage/browser/[bucket-id]/
bucket = client.get_bucket('mlops_1')


# **CloudStorageにファイルをアップロードする**

# In[11]:


# 保存ファイル名（フォルダを指定することもできる）
save_file_name = 'df.csv'
# アップロードしたいファイルのパス
uploaded_file_path = './data/df.csv'
blob = bucket.blob(save_file_name)
blob.upload_from_filename(filename=uploaded_file_path)

