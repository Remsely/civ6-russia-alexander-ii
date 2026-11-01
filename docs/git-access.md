# GitHub: CLI и авторизация

В этом проекте для операций GitHub используется GitHub CLI (`gh`), для передачи коммитов — обычный Git по HTTPS с авторизацией `gh`. Исполняемый файл: `C:/Program Files/GitHub CLI/gh.exe`. Проверено в этой среде: активная авторизация Remsely есть в keyring, SSH push/fetch возвращает Permission denied (publickey). Не начинать с SSH только потому, что origin записан как git@github.com.

Проверить доступ без вывода токена:

```powershell
& 'C:/Program Files/GitHub CLI/gh.exe' auth status
```

Авторизованный HTTPS fetch/push без изменения origin или глобального Git-конфига:

```powershell
git -c 'credential.helper=' -c 'credential.helper=!"C:/Program Files/GitHub CLI/gh.exe" auth git-credential' fetch https://github.com/Remsely/civ6-russia-alexander-ii.git <ветка>
git -c 'credential.helper=' -c 'credential.helper=!"C:/Program Files/GitHub CLI/gh.exe" auth git-credential' push https://github.com/Remsely/civ6-russia-alexander-ii.git HEAD:refs/heads/<ветка>
```

Вместо `<ветка>` подставлять проверенную целевую ветку. Не вызывать gh auth token и не выводить учетные данные. Если авторизация недоступна, сообщить об этом; не настраивать новый аккаунт и не менять Git-идентичность самостоятельно. Наличие авторизации не заменяет разрешения пользователя на публикацию.

Скиллы `.agents/skills/` синхронизируются в `.claude/skills/` и `.zcode/skills/`. Общие правила AGENTS.md/CLAUDE.md автоматически не зеркалируются: соответствующие положения обновляются вручную, а одинаковые процедуры, как эта, выносятся в общий документ. Скрипт синхронизации скиллов не перезаписывает эти файлы и MCP-конфиги. В текущем worktree в `.zcode/` есть только зеркало скиллов; отдельного файла общих правил Z Code здесь нет. Это не доказывает, какой корневой файл инструкций читает установленный Z Code.
