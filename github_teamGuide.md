# GitHub 協作指南 (團隊版)

這份文件整理了多人合作專案時，如何在 GitHub 上協作的流程、常見問題解答 (Q\&A)，以及 Pull Request (PR) 的建議時機。

---

## 🌳 分支規則

* `main` 分支：最穩定版本，不能直接開發。
* 每個人要開 **自己的分支** 來開發，例如：

  * `feature-login`
  * `feature-schedule`
  * `fix-bug-database`

---

## 🔧 基本流程

### 1. 取得最新程式碼

```bash
git checkout main
git pull origin main
```

### 2. 建立新分支

```bash
git checkout -b feature-功能名稱
git push origin feature-功能名稱
```

### 3. 在分支上開發並提交

```bash
git add .
git commit -m "新增登入功能"
git push origin feature-功能名稱
```

### 4. 建立 Pull Request (PR)

1. 上 GitHub → 開一個 PR，把你的分支合併到 `main`。
2. 其他人可以在 PR 頁面看到你修改的程式，並留言或按 ✅。
3. PR 通過後，才能合併到 `main`。

### 5. 更新本地程式碼

別人合併後，你要更新：

```bash
git checkout main
git pull origin main
```

---

## 👀 查看隊友的程式

### 看 GitHub 上的 PR (**最推薦**)

* 可以直接看到紅/綠的差異。

### 切換到隊友的分支

```bash
git fetch origin
git checkout feature-隊友的分支
```

回到自己分支：

```bash
git checkout feature-我的分支
```

### 看差異

```bash
git diff main..feature-隊友的分支
```

---

## ⏪ 回到舊版本

* **暫時查看某個 commit**

```bash
git checkout <commit_id>
```

* **從舊版本建立新分支**

```bash
git checkout -b old-feature <commit_id>
```

* **讓分支回到舊版本 (⚠️會覆蓋掉新 commit)**

```bash
git reset --hard <commit_id>
```

---

## 📌 Pull Request 時機 (團隊約定)

### 建議什麼時候發 PR？

1. **功能完成的時候**

   * 例如：登入功能寫完。

2. **功能做到可運行的階段**

   * 即使還沒 100%，但能跑、能測試，就可以先發。

3. **修 bug 或小修改**

   * README、typo、小修正。

### 不建議

* 一大堆修改塞在一個 PR。
* 還沒完成的功能硬塞進 main。

### 規範建議

* 每個人至少 **1–2 天發一次 PR**。
* PR 標題要清楚：

  * `feat: add user login API`
  * `fix: schedule timezone bug`
  * `docs: update README`

---

## ❓ 常見問題 Q\&A

### Q1. `git fetch origin` 是什麼？

* 更新遠端的最新紀錄，但不會改你檔案。

### Q2. 如果 merge 之後想回到自己版本？

* 還沒 commit → `git merge --abort`。
* 已經 commit → `git reset --hard <commit_id>`。

### Q3. merge 和 commit 有什麼差？

* commit = 存自己修改。
* merge = 把別人分支合進來，可能會自動產生 merge commit。

### Q4. 為什麼要先 `git checkout main && git pull origin main`？

* 確保 main 是最新的，避免衝突。
* 再從最新 main 開新分支。

### Q5. 如果沒有分支，只想更新程式？

* `git pull origin main` 就能讓 main 最新，但多人合作不建議。

### Q6. 切到隊友分支後，怎麼回自己分支？

```bash
git checkout feature-myname
```

### Q7. 沒 commit 的修改怎麼辦？

* 先 commit，或用 stash：

```bash
git stash
git checkout feature-teammate
git checkout feature-myname
git stash pop
```

---

## 📝 Git 常用指令大全

### 初始化與下載

```bash
git clone <repo-url>       # 複製 GitHub 專案到本地端
```

### 狀態檢查

```bash
git status                 # 查看當前修改、新檔案、刪除檔案
git log --oneline          # 查看 commit 歷史 (簡短模式)
```

### 新增與提交

```bash
git add .                  # 新增所有修改檔案到暫存區
git commit -m "訊息"       # 建立 commit (只存在本地端)
```

### 差異比較

```bash
git diff                   # 比較尚未 staged 的修改
git diff --cached          # 比較已 staged 的修改
git diff commitA commitB -- <檔案>  # 比較兩個 commit 的檔案差異
```

### 還原與回退

```bash
git checkout <commit> -- <檔案>   # 把指定檔案還原到某個 commit
git reset --hard <commit>         # 整個專案退回到某個 commit (不可逆)
```

### 分支操作

```bash
git branch                        # 查看目前與所有分支
git checkout -b <branch>          # 建立並切換到新分支
```

### 與遠端互動

```bash
git push origin <branch>          # 推送分支到 GitHub
git push origin main              # 推送 main 分支到 GitHub
git pull                          # 抓取遠端更新並合併
```

---

## ⚠️ 注意事項

* `git reset --hard`：會永久刪除該 commit 之後的歷史，請小心使用。
* `git push`：建議明確指定 `origin <branch>`，避免誤會覆蓋。
* `git diff`：比較時最好指定兩個 commit，例如：

  ```bash
  git diff <commitA> <commitB> -- <檔案>
  ```

---

## 📊 Git 工作流程圖

```mermaid
flowchart TD
    A[git clone <repo-url>] --> B[git status]
    B --> C[修改檔案]
    C --> D[git add .]
    D --> E[git commit -m "訊息"]
    E --> F{需要推送嗎?}
    F -- Yes --> G[git push origin <branch>]
    F -- No --> H[留在本地端]
    G --> I[GitHub 遠端更新]
    I --> J[git pull] --> B
```

---

這樣做可以確保：

* main 永遠乾淨
* 每個功能有自己的分支
* PR 流程清楚，大家都能看到彼此的修改 🚀
