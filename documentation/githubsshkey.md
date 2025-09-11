Add SSH Key to GitHub

  1. Copy this SSH key:
  ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICGaHioEWnC+JQIIU4Ra3byoaho3qGLh6dHey1IthCC2
  2dbatkv@gmail.com
  2. Add to GitHub:
    - Go to GitHub → Settings → SSH and GPG keys
    - Click "New SSH key"
    - Title: "CaveMapper Development"
    - Paste the key above
    - Click "Add SSH key"
  3. Update remote URL to use SSH:

● Bash(git remote set-url origin git@github.com:2dbatkv/cave-survey-pmvp.git)
