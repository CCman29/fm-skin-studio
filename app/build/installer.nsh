; FM Skin Studio installer additions: an optional Game Link page (Windows only).
; Silent installs (auto-updates) skip pages, so Game Link is only ever set up when the user ticks the box.

!macro customPageAfterChangeDir
  !ifndef BUILD_UNINSTALLER
    Var GameLinkBox
    Var GameLinkChoice

    Page custom GameLinkPage GameLinkLeave

    Function GameLinkPage
      !insertmacro MUI_HEADER_TEXT "Game Link for the Advanced Editor (optional)" "Work with FM27 directly while you edit"
      nsDialogs::Create 1018
      Pop $0
      ${If} $0 == error
        Abort
      ${EndIf}
      ${NSD_CreateLabel} 0 0 100% 96u "Game Link lets the Advanced Editor work with Football Manager 27 directly: it reloads your skin inside the game when you save, shows the game's screen as you edit, and can recolour club and player names for light skins. The rest of FM Skin Studio works without it.$\r$\n$\r$\nIt adds the free, open-source BepInEx mod loader and a small helper to your FM27 folder. It never touches your saves. Mods aren't supported by Sports Interactive; you can remove Game Link at any time from the Advanced Editor.$\r$\n$\r$\nFootball Manager 27 must be closed while it's set up."
      Pop $0
      ${NSD_CreateCheckbox} 0 104u 100% 12u "Set up Game Link in FM27"
      Pop $GameLinkBox
      ${If} $GameLinkChoice == ${BST_CHECKED}
        ${NSD_Check} $GameLinkBox
      ${EndIf}
      nsDialogs::Show
    FunctionEnd

    Function GameLinkLeave
      ${NSD_GetState} $GameLinkBox $GameLinkChoice
    FunctionEnd
  !endif
!macroend

!macro customInstall
  ${If} $GameLinkChoice == ${BST_CHECKED}
    DetailPrint "Setting up Game Link in FM27..."
    gamelink_retry:
    nsExec::ExecToStack '"$INSTDIR\resources\core\fmskin-core.exe" gamelink-install'
    Pop $0
    Pop $1
    ${If} $0 == 0
      DetailPrint "$1"
    ${Else}
      MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Game Link wasn't set up:$\r$\n$\r$\n$1$\r$\nFix this and choose Retry, or choose Cancel to set it up later from the Advanced Editor." /SD IDCANCEL IDRETRY gamelink_retry
      DetailPrint "Game Link wasn't set up: $1"
    ${EndIf}
  ${EndIf}
!macroend
