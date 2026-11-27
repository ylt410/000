import CryptoKit
import Foundation

enum CacheMaintenance {
    static func beginImport(_ url: URL) {}
    static func removeImport(_ url: URL) { try? FileManager.default.removeItem(at: url) }
}

enum AppLanguage {
    static func choose(_ text: String) -> String { text }
    static func interpolate(_ text: String, _ args: [String]) -> String { text }
}

struct InstallError: Error {
    enum Kind { case unsupported, sourceUnreadable, corrupted, passwordProtected }
    let message: String
    init(_ kind: Kind, _ message: String) { self.message = message }
}

enum Theme { static let appVersion = "installer-verifier" }
enum VerifyPaths {
    static let workspace = FileManager.default.temporaryDirectory
        .appendingPathComponent("fivestarport-verify-" + UUID().uuidString)
    static let mods = workspace.appendingPathComponent("Mods")
}

struct VerificationError: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

struct Manifest: Decodable {
    struct Entry: Decodable { let sha256: String }
    struct Companion: Decodable { let name: String; let sha256: String }
    let sha256: String
    let root_folder: String
    let targets: [String: Entry]
    let companion: Companion?
}

func sha256(_ url: URL) throws -> String {
    let source = try FileHandle(forReadingFrom: url)
    defer { try? source.close() }
    var hash = SHA256()
    while let bytes = try source.read(upToCount: 1 << 20), !bytes.isEmpty {
        hash.update(data: bytes)
    }
    return hash.finalize().map { String(format: "%02x", $0) }.joined()
}

@main struct VerifyInstaller {
    static func main() {
        do {
            try run()
        } catch {
            fputs("Installation verification failed: \(error)\n", stderr)
            exit(1)
        }
    }

    static func run() throws {
        let args = CommandLine.arguments
        guard args.count == 4 else {
            throw VerificationError("usage: verify-install Full.zip FULL_RESULTS.json receipt.json")
        }
        let fm = FileManager.default
        let input = URL(fileURLWithPath: args[1])
        let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: URL(fileURLWithPath: args[2])))
        guard !manifest.targets.isEmpty, try sha256(input) == manifest.sha256 else {
            throw VerificationError("archive digest or target map does not match manifest")
        }
        try fm.createDirectory(at: VerifyPaths.workspace, withIntermediateDirectories: false,
                               attributes: [.posixPermissions: 0o700])
        defer { try? fm.removeItem(at: VerifyPaths.workspace) }
        let unpacked = try ModInstaller.unpack(input)
        defer { try? fm.removeItem(at: unpacked) }
        let plan = ModInstaller.plan(folder: unpacked, name: "VerifiedPackage", index: .init())
        let expectedKinds: Set<String> = manifest.companion == nil ? ["oiv"] : ["oiv", "asi"]
        let expectedPlugins = manifest.companion.map { [$0.name] } ?? []
        let plannedPlugins = plan.items.filter { $0.target.lowercased().hasSuffix(".asi") }.map { $0.target }
        guard plan.kinds == expectedKinds, !plan.unsupported, plan.skipped.isEmpty, plannedPlugins == expectedPlugins else {
            throw VerificationError("unexpected import plan or skipped files")
        }
        let installed = try ModInstaller.install(plan)
        if let companion = manifest.companion {
            guard try sha256(installed.appendingPathComponent(companion.name)) == companion.sha256 else {
                throw VerificationError("installed plugin digest mismatch")
            }
        }

        let receipt = VerifyPaths.workspace.appendingPathComponent("native.json")
        let cache = VerifyPaths.workspace.appendingPathComponent("NativeCache")
        let native = Process()
        native.executableURL = URL(fileURLWithPath: args[0]).standardizedFileURL
            .deletingLastPathComponent().appendingPathComponent("verify-oiv")
        native.arguments = [VerifyPaths.mods.path, cache.path, receipt.path]
        try native.run()
        native.waitUntilExit()
        guard native.terminationStatus == 0 else { throw VerificationError("native OpenIV expansion failed") }
        let entries = try JSONDecoder().decode([String: String].self, from: Data(contentsOf: receipt))
        guard Set(entries.keys) == Set(manifest.targets.keys) else {
            throw VerificationError("expanded targets do not match the manifest")
        }

        let root = installed.appendingPathComponent(manifest.root_folder).appendingPathComponent("content/files").resolvingSymlinksInPath()
        for (target, entry) in manifest.targets {
            let actual = URL(fileURLWithPath: entries[target]!).resolvingSymlinksInPath()
            let expected = root.appendingPathComponent(target).standardizedFileURL
            guard actual.path == expected.path, actual.path.hasPrefix(root.path + "/"),
                  try sha256(actual) == entry.sha256 else {
                throw VerificationError("expanded path or payload digest mismatch for \(target)")
            }
        }
        let result: [String: Any] = [
            "passed": true,
            "full_zip_sha256": manifest.sha256,
            "verified_payloads": entries.count,
            "installed_plugins": expectedPlugins.count,
            "addon_packs": entries.keys.filter { $0.hasPrefix("update/x64/dlcpacks/") && $0.hasSuffix("/dlc.rpf") }.count,
            "iphone_tested": false
        ]
        try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
            .write(to: URL(fileURLWithPath: args[3]), options: .atomic)
    }
}
