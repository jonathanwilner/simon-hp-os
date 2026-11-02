;;; emacs-desktop-mode.el --- Follow Goran's desktop mode -*- lexical-binding: t; -*-

;; HP-OS writes GTK settings when the desktop changes mode.  The old DMS
;; palette file can survive a session change and must not select Emacs's mode.
(defvar goran/desktop-mode-timer nil)
(defvar goran/desktop-mode-current nil)

(defun goran/desktop-mode-sync ()
  "Apply the desktop mode to the shared daemon and its current and new frames."
  (condition-case err
      (let ((settings (expand-file-name
                       "gtk-3.0/settings.ini"
                       (or (getenv "XDG_CONFIG_HOME") "~/.config"))))
        (when (file-readable-p settings)
          (let ((mode (with-temp-buffer
                        (insert-file-contents settings)
                        (goto-char (point-min))
                        (when (re-search-forward
                               "^[ \t]*gtk-application-prefer-dark-theme[ \t]*=[ \t]*\\([01]\\)[ \t]*$"
                               nil t)
                          (if (equal (match-string 1) "1") 'dark 'light)))))
            (when (and mode
                       (not (eq mode
                                (if (boundp 'patrl/desktop-theme-current-palette)
                                    (plist-get patrl/desktop-theme-current-palette :mode)
                                  goran/desktop-mode-current))))
              (if (fboundp 'fleet-emacs-style-apply)
                  (fleet-emacs-style-apply
                   (if (eq mode 'dark) 'rio-dark 'harmonyos-light))
                (mapc #'disable-theme custom-enabled-themes)
                (load-theme (if (eq mode 'dark) 'modus-vivendi 'modus-operandi) t))
              (setq goran/desktop-mode-current mode)))))
    (error (message "Goran desktop theme: %s" (error-message-string err)))))

(unless (fboundp 'fleet-emacs-style-apply)
  (load (expand-file-name
         "emacs-fleet-style/style.el"
         (or (getenv "XDG_DATA_HOME") "~/.local/share")) t t))
(when (timerp goran/desktop-mode-timer)
  (cancel-timer goran/desktop-mode-timer))
(goran/desktop-mode-sync)
(setq goran/desktop-mode-timer
      (run-with-timer 2 2 #'goran/desktop-mode-sync))

(provide 'goran-desktop-mode)
;;; emacs-desktop-mode.el ends here
