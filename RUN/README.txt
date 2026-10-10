RUN folder: everything you need, in one place. Double-click a .cmd file (or run the .ps1 in PowerShell). Nothing here needs you to open or change any other folder.

  CHECK.cmd             is everything ready? (Python, database, ports, space on D, which safety copies can be restored)
  START.cmd             start the database service, PesoWeb, the screens (http://127.0.0.1:4200) and the dashboard
  SAVE-SNAPSHOT.cmd     save a safety copy of the whole database on drive D (asks for a name)
  AGENT-REAL.cmd        start the AI helper for the real company 520 Minimart (asks for the password); leave the window open.
                        It serves Run now for AI Monitoring, AI Pricing, AI Product Loss Prevention, AI Replenish, AI Customer Mission
  RESTORE-SNAPSHOT.cmd  put the database back to a safety copy (lists them and whether each can be restored now; saves the present state first).
                        It REFUSES a copy whose database structure differs from today's (a table, column or stored procedure changed since),
                        and a hand-made copy with no structure note (SAVE-SNAPSHOT writes <name>.structure.txt beside every copy).
  STOP.cmd              stop PesoWeb, the screens and the dashboard
  CREDENTIALS.txt       every login and where each secret is kept (plain text, git-ignored: never commit or share it)

Order for a real test: CHECK, START, then SAVE-SNAPSHOT, then sign in at http://127.0.0.1:4200, then AGENT-REAL.
After any change to the database structure (a migration), save a new copy: older copies can no longer be restored.
Full step-by-step: Docs\real-use-guide.md
