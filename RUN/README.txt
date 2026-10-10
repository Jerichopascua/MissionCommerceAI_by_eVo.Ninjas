RUN folder: everything you need, in one place. Double-click a .cmd file (or run the .ps1 in PowerShell). Nothing here needs you to open or change any other folder.

  START.cmd             start PesoWeb, the screens (http://127.0.0.1:4200) and the dashboard
  SAVE-SNAPSHOT.cmd     save a safety copy of the whole database on drive D (asks for a name)
  AGENT-REAL.cmd        start the AI helper for the real company 520 Minimart (asks for the password); leave the window open
  RESTORE-SNAPSHOT.cmd  put the database back to a safety copy (asks which; saves the present state first)
  STOP.cmd              stop PesoWeb, the screens and the dashboard

Order for a real test: START, then SAVE-SNAPSHOT, then sign in at http://127.0.0.1:4200, then AGENT-REAL.
Full step-by-step: Docs\real-use-guide.md
