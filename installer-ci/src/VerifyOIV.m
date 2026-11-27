#import <Foundation/Foundation.h>

static NSString *verificationCache;
#import "NativeOIV.generated.m"

void pg_log(const char *message) { (void)message; }
void pg_mod_path_used(const char *path) { (void)path; }

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 4 && argc != 5) return 2;
        verificationCache = @(argv[2]);
        bool needsGame = false;
        NSArray<NSString *> *packages = nil;
        NSArray<NSArray *> *entries = pg_oiv_expand(@(argv[1]), ^NSString *(NSString *path) {
            return argc == 5 && [path isEqualToString:@"common/data/gameconfig.xml"] ? @(argv[4]) : nil;
        }, argc == 5, &needsGame, &packages);
        if (needsGame || packages.count != 1 || entries.count == 0) return 1;
        NSMutableDictionary<NSString *, NSString *> *targets = [NSMutableDictionary dictionary];
        NSMutableSet<NSString *> *seen = [NSMutableSet set];
        for (NSArray *entry in entries) {
            NSString *target = entry[0];
            if ([seen containsObject:target.lowercaseString]) return 1;
            [seen addObject:target.lowercaseString];
            targets[target] = entry[1];
        }
        NSData *data = [NSJSONSerialization dataWithJSONObject:targets options:NSJSONWritingSortedKeys error:NULL];
        return [data writeToFile:@(argv[3]) atomically:YES] ? 0 : 1;
    }
}
