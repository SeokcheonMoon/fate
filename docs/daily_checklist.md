## STEP 1: 프로젝트 기획서 작성 (README 수준)

#### GitHub Repository 생성
- git config --global user.name "깃허브이름"
- git config --global user.email "깃허브이메일"

| 명령                    | 적용 범위            |
| --------------------- | ---------------- |
| `git config --global` | 내 PC 모든 Git 프로젝트 |
| `git config`          | 현재 프로젝트만         |

#### 프로젝트 폴더 구조 생성
#### requirements.txt 작성
#### .gitignore 작성
#### Python 가상환경 생성 및 활성화
- 가상환경 생성
    + py -m venv .venv

- 가상환경 활성화 
    + .venv\Scripts\Activate.ps1

- .venv = 내 컴퓨터 안의 실제 개발 환경 (공유 X)

- 라이브러리 설치
    + pip install --upgrade pip
    + pip install -r requirements.txt


# Git Repository Reset & Re-commit Guide

프로젝트 진행 중 Git 이력이 꼬이거나 불필요한 파일/상위 폴더가 잘못 추적되었을 때, Git 설정을 완전 초기화하고 원격 저장소(`https://github.com/SeokcheonMoon/fate`)에 다시 연결하는 절차입니다.

---

## 1. 기존 Git 설정 제거
현재 프로젝트 내의 기존 Git 이력 및 추적 정보를 삭제합니다. (실제 코드 파일은 유지됩니다.)

```bash
# Mac / Linux / Git Bash
rm -rf .git

# Windows (PowerShell)
Remove-Item -Recurse -Force .git

# Git 저장소 초기화
git init

# 기본 브랜치 이름을 main으로 변경
git branch -M main

# 원격 저장소 주소 연결
git remote add origin [https://github.com/SeokcheonMoon/fate](https://github.com/SeokcheonMoon/fate)

# 연결 확인
git remote -v

# 전체 파일 스테이징
git add .

# 추적 대상 파일 목록 확인
git status

# 커밋 생성
git commit -m "Initial commit: Reinitialize repository & fix folder structure"

# 원격 저장소로 강제 푸시 (이전 이력 덮어쓰기)
git push -u origin main --force

```


## 주요 명령어 요약

| 단계 | 명령어 | 설명 |
| --- | --- | --- |
| **1. 삭제** | `rm -rf .git` | 기존 Git 추적 정보 제거 |
| **2. 초기화** | `git init && git branch -M main` | Git 재시작 및 main 브랜치 설정 |
| **3. 연결** | `git remote add origin <URL>` | GitHub 저장소 주소 등록 |
| **4. 커밋** | `git add . && git commit -m "msg"` | 파일 추적 및 커밋 메시지 작성 |
| **5. 푸시** | `git push -u origin main --force` | 원격 저장소에 강제 덮어쓰기 |