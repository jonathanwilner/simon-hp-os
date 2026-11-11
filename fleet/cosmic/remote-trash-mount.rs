// Background trash discovery must not synchronously probe remote services.
// Mount-boundary detection and explicit file operations retain every mount.
fn skip_background_trash_discovery(filesystem: &str) -> bool {
    matches!(
        filesystem,
        "autofs"
            | "9p"
            | "nfs"
            | "nfs4"
            | "cifs"
            | "smb3"
            | "sshfs"
            | "fuse.sshfs"
            | "davfs"
            | "davfs2"
            | "fuse.davfs"
            | "fuse.rclone"
            | "fuse.s3fs"
            | "ceph"
            | "fuse.ceph"
            | "glusterfs"
            | "fuse.glusterfs"
            | "afs"
    )
}

#[cfg(test)]
mod hp_os_remote_trash_tests {
    use super::skip_background_trash_discovery;

    #[test]
    fn remote_and_automount_filesystems_are_not_probed() {
        for filesystem in ["9p", "autofs", "fuse.sshfs", "nfs", "nfs4", "cifs", "smb3", "fuse.rclone"] {
            assert!(skip_background_trash_discovery(filesystem), "{filesystem}");
        }
    }

    #[test]
    fn local_disk_usb_and_local_fuse_trash_remain_discoverable() {
        for filesystem in ["ext4", "btrfs", "xfs", "vfat", "exfat", "ntfs3", "fuseblk", "fuse.gocryptfs"] {
            assert!(!skip_background_trash_discovery(filesystem), "{filesystem}");
        }
    }
}
