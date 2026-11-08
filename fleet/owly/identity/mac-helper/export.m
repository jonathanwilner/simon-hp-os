// Export the signed-in user's AirDrop identity for OM Drop.
// Requires Apple's private Sharing entitlement and keychain access group.
// This does not change SIP, AMFI, keychain ACLs, or the account identity.
#import <Foundation/Foundation.h>
#import <Security/Security.h>
#import <dlfcn.h>
#import <sys/stat.h>

@interface SFAppleIDValidationRecord : NSObject
- (NSData *)data;
@end

@interface SFAppleIDIdentity : NSObject
- (NSData *)certificatePersistentReference;
- (NSData *)intermediateCertificatePersistentReference;
- (NSData *)privateKeyPersistentReference;
@end

@interface SFAppleIDAccount : NSObject
- (SFAppleIDIdentity *)identity;
- (SFAppleIDValidationRecord *)validationRecord;
@end

@interface SFAppleIDClient : NSObject
- (SFAppleIDAccount *)myAccountWithError:(NSError **)error;
- (void)invalidate;
@end

static CFTypeRef lookup(NSData *reference, CFStringRef itemClass) {
    if (!reference.length) return NULL;
    NSDictionary *query = @{
        (id)kSecClass: (__bridge id)itemClass,
        (id)kSecValuePersistentRef: reference,
        (id)kSecReturnRef: @YES,
        (id)kSecUseAuthenticationUI: (id)kSecUseAuthenticationUIFail,
    };
    CFTypeRef result = NULL;
    OSStatus status = SecItemCopyMatching((__bridge CFDictionaryRef)query, &result);
    if (status) fprintf(stderr, "AirDrop keychain lookup failed: %d\n", (int)status);
    return status ? NULL : result;
}

static NSData *pem(NSData *data, NSString *type) {
    NSString *base64 = [data base64EncodedStringWithOptions:
        NSDataBase64Encoding64CharacterLineLength | NSDataBase64EncodingEndLineWithLineFeed];
    return [[NSString stringWithFormat:@"-----BEGIN %@-----\n%@\n-----END %@-----\n",
             type, base64, type] dataUsingEncoding:NSUTF8StringEncoding];
}

static BOOL writeProtected(NSData *data, NSString *directory, NSString *name) {
    NSString *path = [directory stringByAppendingPathComponent:name];
    if (![data writeToFile:path options:NSDataWritingAtomic error:NULL]) return NO;
    return chmod(path.fileSystemRepresentation, 0600) == 0;
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 2) {
            fprintf(stderr, "Usage: omdrop-export-apple-identity NEW_OUTPUT_DIRECTORY\n");
            return 2;
        }
        umask(0077);
        SecKeychainSetUserInteractionAllowed(false);
        NSString *directory = [NSString stringWithUTF8String:argv[1]];
        if ([[NSFileManager defaultManager] fileExistsAtPath:directory]) {
            fprintf(stderr, "Output directory already exists; refusing to overwrite.\n");
            return 2;
        }
        if (!dlopen("/System/Library/PrivateFrameworks/Sharing.framework/Sharing", RTLD_NOW)) {
            fprintf(stderr, "Sharing framework is unavailable.\n");
            return 3;
        }
        SFAppleIDClient *client = [[NSClassFromString(@"SFAppleIDClient") alloc] init];
        NSError *error = nil;
        SFAppleIDAccount *account = [client myAccountWithError:&error];
        if (!account) {
            fprintf(stderr, "AirDrop account unavailable: %s (%ld)\n",
                    error.domain.UTF8String, (long)error.code);
            return 4;
        }
        SFAppleIDIdentity *identity = [account identity];
        NSData *record = [[account validationRecord] data];
        SecCertificateRef leaf = (SecCertificateRef)lookup(
            [identity certificatePersistentReference], kSecClassCertificate);
        SecCertificateRef intermediate = (SecCertificateRef)lookup(
            [identity intermediateCertificatePersistentReference], kSecClassCertificate);
        SecKeyRef key = (SecKeyRef)lookup([identity privateKeyPersistentReference], kSecClassKey);
        if (!leaf || !intermediate || !key || !record.length) {
            fprintf(stderr, "AirDrop account does not expose a complete identity.\n");
            [client invalidate];
            return 5;
        }
        CFErrorRef keyError = NULL;
        CFDataRef keyData = SecKeyCopyExternalRepresentation(key, &keyError);
        if (!keyData) {
            fprintf(stderr, "AirDrop private-key export failed: %ld\n",
                    keyError ? (long)CFErrorGetCode(keyError) : -1L);
            [client invalidate];
            return 6;
        }
        CFDataRef leafData = SecCertificateCopyData(leaf);
        CFDataRef intermediateData = SecCertificateCopyData(intermediate);
        NSMutableData *certificates = [NSMutableData dataWithData:
            pem((__bridge NSData *)leafData, @"CERTIFICATE")];
        [certificates appendData:pem((__bridge NSData *)intermediateData, @"CERTIFICATE")];
        if (mkdir(directory.fileSystemRepresentation, 0700)) {
            perror("Creating protected output directory");
            return 7;
        }
        BOOL ok = writeProtected(certificates, directory, @"certificate.pem") &&
            writeProtected(pem((__bridge NSData *)keyData, @"RSA PRIVATE KEY"), directory, @"key.pem") &&
            writeProtected(record, directory, @"validation_record.cms");
        CFRelease(keyData); CFRelease(leafData); CFRelease(intermediateData);
        CFRelease(leaf); CFRelease(intermediate); CFRelease(key);
        [client invalidate];
        if (!ok) {
            fprintf(stderr, "Output write failed; incomplete files remain in protected directory.\n");
            return 8;
        }
        printf("Exported AirDrop certificate, key and %lu-byte validation record.\n",
               (unsigned long)record.length);
        return 0;
    }
}
