# A running Niri session can retain the previous package's data directories
# when its HP-OS shell is upgraded. Qt merges matching icon themes from every
# directory and can select old PNG entries ahead of the current package.
hpos_clean_data_dirs() {
    local packaging="$1" current_store entry store cleaned=""
    current_store="${packaging%/share/hp-os/packaging}"
    # Source installations have no Nix store generation to select.
    [[ "$current_store" == /nix/store/*-hp-os-* ]] || return 0
    local -a entries
    IFS=: read -r -a entries <<< "${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
    for entry in "${entries[@]}"; do
        case "$entry" in
            /nix/store/*-hp-os-*/share|/nix/store/*-hp-os-*/share/hp-os|/nix/store/*-hp-os-*/share/hp-os/packaging/files/data)
                store="${entry%%/share*}"
                [[ "$store" == "$current_store" ]] || continue
                ;;
        esac
        [[ -n "$entry" ]] || continue
        case ":$cleaned:" in *":$entry:"*) continue ;; esac
        cleaned+="${cleaned:+:}$entry"
    done
    export XDG_DATA_DIRS="$cleaned"
}
