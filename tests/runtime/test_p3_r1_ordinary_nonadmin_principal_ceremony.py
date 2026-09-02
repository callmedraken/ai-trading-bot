"""Compile the exact disabled helper; exercise only generated in-process fakes.

Every subprocess uses Windows PowerShell 5.1, -NoProfile, -NonInteractive.
RemoteSigned is process-scoped only; no installed execution policy is changed.
No password is created, prompted for, marshalled, or passed through Python.
Generated sources and fake evidence belong exclusively to pytest's tmp_path.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs"
WRAPPER = ROOT / "scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1"
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
EVIDENCE_ROOT = Path(r"F:\p3-r1-ordinary-nonadmin-principal-v2")

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows 5.1 compile gate")


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def powershell(script: str, *, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "RemoteSigned",
            "-Command",
            "$ErrorActionPreference='Stop'; " + script,
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_wrapper_syntax_compile_and_inert_invocation() -> None:
    before = EVIDENCE_ROOT.exists()
    parsed = powershell(
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"{ps_quote(WRAPPER)},[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count) { throw 'PARSE_FAILED' }; 'PARSE_PASS'"
    )
    assert parsed.returncode == 0, parsed.stderr
    assert parsed.stdout.strip() == "PARSE_PASS"
    compiled = powershell(
        f"$source=[IO.File]::ReadAllText({ps_quote(HELPER)}); "
        "Add-Type -TypeDefinition $source -ReferencedAssemblies "
        "System.dll,System.Core.dll,([System.Management.Automation.PSObject]."
        "Assembly.Location) -ErrorAction Stop; 'COMPILE_PASS'"
    )
    assert compiled.returncode == 0, compiled.stderr
    assert compiled.stdout.strip() == "COMPILE_PASS"
    result = powershell(f"& {ps_quote(WRAPPER)}")
    assert result.returncode == 0, result.stderr
    assert "ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false" in result.stdout
    assert "password_prompt=false; native_dispatch=false" in result.stdout
    assert "evidence_root_creation=false" in result.stdout
    assert EVIDENCE_ROOT.exists() == before


def test_wrapper_rejects_arguments_preloaded_types_and_changed_source(
    tmp_path: Path,
) -> None:
    supplied = powershell(f"& {ps_quote(WRAPPER)} -AccountName OtherUser")
    assert supplied.returncode != 0
    preload = powershell(
        "Add-Type 'namespace P3R1OrdinaryPrincipalV1 { "
        "public static class Launcher {} }'; "
        f"& {ps_quote(WRAPPER)}"
    )
    assert preload.returncode != 0
    assert "already loaded" in preload.stderr
    local_wrapper = tmp_path / WRAPPER.name
    local_wrapper.write_bytes(WRAPPER.read_bytes())
    (tmp_path / HELPER.name).write_bytes(HELPER.read_bytes() + b"\n// changed\n")
    changed = powershell(f"& {ps_quote(local_wrapper)}")
    assert changed.returncode != 0
    assert "hash mismatch" in changed.stderr


def test_frozen_source_surface_and_secure_input_order() -> None:
    source = HELPER.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    assert "const bool ACCOUNT_EFFECT_EXECUTION_AUTHORIZED = false;" in source
    assert "NOT-AUTHORIZED-P3R1-ORDINARY-NONADMIN-PRINCIPAL-V1" in source
    assert hashlib.sha256(HELPER.read_bytes()).hexdigest() in wrapper
    for forbidden in (
        "New-LocalUser",
        "Add-LocalGroupMember",
        "NetUserDel",
        "NetUserSetInfo",
        "Remove-LocalUser",
        "Set-LocalUser",
        "Enable-LocalUser",
        "Disable-LocalUser",
        "Remove-LocalGroupMember",
        "NetLocalGroupDelMembers",
        "SamCreate",
        "SamDelete",
        "LogonUser",
        "ImpersonateLoggedOnUser",
        "Start-Transcript",
        "PtrToString",
        "NetworkCredential",
        "GetEnvironmentVariable",
        "NCrypt",
        "SetSecurityInfo",
        "SetNamedSecurityInfo",
        "SetFileSecurity",
        "Set-Acl",
        "Directory.CreateDirectory",
    ):
        assert forbidden not in source + wrapper
    required = {
        "NetUserAdd",
        "NetUserGetInfo",
        "NetUserEnum",
        "NetUserGetLocalGroups",
        "NetLocalGroupAddMembers",
        "NetApiBufferFree",
        "NetApiBufferSize",
        "LookupAccountSidW",
        "LookupAccountNameW",
        "OpenProcessToken",
        "OpenThreadToken",
        "GetTokenInformation",
        "LookupPrivilegeNameW",
        "IsValidSid",
        "GetLengthSid",
        "ConvertSidToStringSidW",
        "LsaOpenPolicy",
        "LsaEnumerateAccountRights",
        "LsaFreeMemory",
        "LsaClose",
        "CreateDirectoryW",
        "GetFileAttributesW",
        "CloseHandle",
        "LocalFree",
        "GetVolumeInformationByHandleW",
        "GetFinalPathNameByHandleW",
        "GetDriveTypeW",
    }
    bindings = set(re.findall(r"extern\s+[\w<>]+\s+(\w+)\(", source))
    assert required <= bindings
    assert source.count("Native.NetUserAdd(") == 1
    assert source.count("Native.NetLocalGroupAddMembers(") == 1
    body = source.split("internal CreateResult CreateAccount(", 1)[1].split(
        "internal uint AssignUsers(", 1
    )[0]
    assert body.index("Gate.Require();") < body.index("secret.Length")
    assert body.index('journal.BeginDispatch("ACCOUNT_CREATION_ATTEMPTED")') < (
        body.index("Marshal.SecureStringToGlobalAllocUnicode(secret)")
    )
    assert body.count("Marshal.SecureStringToGlobalAllocUnicode(secret)") == 1
    assert body.count("Marshal.ZeroFreeGlobalAllocUnicode(password)") == 1
    assert "finally" in body and "secret.Dispose()" in body
    assert "FreeHGlobal" not in body
    runner = source.split("public static void RunFutureCeremony()", 1)[1]
    assert runner.index("Gate.Require();") < runner.index("new WindowsAdapter()")
    assert wrapper.index("return") < wrapper.index("function Read-P3R1")
    assert r"F:\AI\p3-r1-ordinary-nonadmin-principal-v1" not in source
    assert "p3-r1-ordinary-nonadmin-principal-evidence/v1" not in source
    assert source.count("Native.CreateDirectoryW(") == 1
    root_create = source.split("internal Dictionary<string, object> CreateRoot()", 1)[
        1
    ].split("private void Check()", 1)[0]
    assert root_create.index("Gate.Require();") < root_create.index("ProveAbsent();")
    assert root_create.index("SecurityProof.CreateDescriptor()") < (
        root_create.index("Native.CreateDirectoryW(")
    )
    assert "ref attributes)" in root_create and "inheritHandle = false" in root_create
    assert root_create.index("creation.Begin();") < root_create.index(
        "Native.CreateDirectoryW("
    )
    assert 'new DirectoryGuard(@"F:\\AI")' not in source
    assert "Native.CreateFileW(path, 0x00020080, 3," in source
    assert "0x02200000" in source  # reparse-safe, no-delete-share directory guards
    assert runner.index("native.Observation()") < runner.index("new FixedStore()")


CASES = (
    "fixed_identities",
    "real_gates",
    "absence_complete",
    "absence_statuses",
    "absence_collision",
    "absence_duplicates_malformed",
    "absence_resume_loops",
    "absence_terminal_error",
    "buffer_release_once",
    "buffer_bounds",
    "frozen_user_and_status",
    "account_validation",
    "group_views_and_branches",
    "token_validation",
    "privileges",
    "performance_provenance",
    "graph_cycle_and_alternate",
    "strict_json",
    "evidence_roundtrip",
    "evidence_fields",
    "evidence_order_hash_lifecycle",
    "evidence_sid_drift",
    "stop_terminality",
    "create_pre_retention_failure",
    "users_pre_retention_failure",
    "post_effect_retention_failure",
    "reload_mismatch",
    "fake_success_branches",
    "test_store_no_overwrite_unknown_gaps",
    "protected_root_descriptor",
    "protected_root_inheritance",
    "malformed_security_descriptors",
    "wrong_root_owner",
    "removed_dacl_protection",
    "extra_untrusted_root_ace",
    "unsafe_parent_delete_child",
    "unsafe_parent_security_authority",
    "safe_parent_creation_and_read_rights",
    "wrong_volume_identity",
    "wrong_root_file_identity",
    "root_reparse_substitution",
    "precreated_root_collision",
    "uncertain_root_creation",
    "strict_v2_root_reload",
)


@pytest.fixture(scope="module")
def fake_results(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    temp = tmp_path_factory.mktemp("principal-ceremony-fakes")
    # Compile the unchanged helper and a generated test-only adapter in one
    # assembly, so no production public injection seam is necessary.
    generated = temp / "generated-tests.cs"
    generated.write_text(FAKE_SOURCE, encoding="utf-8")
    result = powershell(
        f"$source=[IO.File]::ReadAllText({ps_quote(HELPER)}) + "
        f"[Environment]::NewLine + [IO.File]::ReadAllText({ps_quote(generated)}); "
        "Add-Type -TypeDefinition $source -ReferencedAssemblies "
        "System.dll,System.Core.dll,([System.Management.Automation.PSObject]."
        "Assembly.Location) -ErrorAction Stop; "
        f"[P3R1OrdinaryPrincipalV1.GeneratedTests]::Run({ps_quote(temp)})"
    )
    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout)
    assert set(values) == set(CASES)
    return values


@pytest.mark.parametrize("case", CASES)
def test_pure_and_fake_contract(case: str, fake_results: dict[str, str]) -> None:
    assert fake_results[case] == "PASS", fake_results[case]


FAKE_SOURCE = r"""
namespace P3R1OrdinaryPrincipalV1
{
    public static class GeneratedTests
    {
        // Synthetic test data only. This suffix is never a predicted native RID.
        private const string TestSid = Gate.MachineSid + "-424242";
        private const string TestCommit = "1111111111111111111111111111111111111111";
        private const string TestTree = "2222222222222222222222222222222222222222";
        private const string TestHelperHash = "3333333333333333333333333333333333333333333333333333333333333333";
        private static void Check(bool ok) { if (!ok) throw new Exception("ASSERTION"); }
        private static void Reject(Action action)
        {
            bool rejected = false;
            try { action(); } catch (Exception) { rejected = true; }
            Check(rejected);
        }
        private static Dictionary<string, object> Host()
        { return J.O("name", Launcher.HOST, "machine_domain_sid", Gate.MachineSid, "os_version", "TEST_ONLY"); }
        private static Dictionary<string, object> Identity()
        { return J.O("sid", Launcher.BUILTIN_USERS_SID, "resolved_name", "Users", "domain", "BUILTIN", "sid_type", 4UL, "roundtrip_passed", true); }
        private static Dictionary<string, object> Group(string sid)
        { return J.O("sid", sid, "name", sid); }
        private static Dictionary<string, object> View(ulong flags, params string[] sids)
        {
            var groups = J.A(sids.Select(s => (object)Group(s)).ToArray()); Proof.Sort(groups, "sid name");
            return J.O("flags", flags, "level", 0UL, "status", 0UL, "entries_read", (ulong)sids.Length, "total_entries", (ulong)sids.Length, "groups", groups);
        }
        private static Dictionary<string, object> Account()
        { return J.O("name", Launcher.CANDIDATE_NAME, "sid", TestSid, "enabled", true, "privilege", 1UL, "flags", 513UL, "machine_domain_sid", Gate.MachineSid,
            "comment", Gate.Comment, "full_name", null, "account_expires", (ulong)UInt32.MaxValue, "defaults_readback_passed", true, "bidirectional_mapping_passed", true); }
        private static Dictionary<string, object> Privilege(string name, ulong attributes)
        { return J.O("name", name, "attributes", attributes, "enabled", (attributes & 2) != 0, "enabled_by_default", (attributes & 1) != 0,
            "removed", (attributes & 4) != 0, "disposition", Proof.PrivilegeDisposition(name)); }
        private static Dictionary<string, object> TokenGroup(string sid, ulong attributes)
        { return J.O("sid", sid, "name", sid, "attributes", attributes, "classification", Proof.Classification(sid)); }
        private static Dictionary<string, object> Token(bool creator)
        {
            var groups = creator ? J.A(TokenGroup(Gate.Administrators, 7)) :
                J.A(TokenGroup(Launcher.BUILTIN_USERS_SID, 7), TokenGroup(Gate.Interactive, 7), TokenGroup("S-1-1-0", 7), TokenGroup("S-1-16-8192", 96));
            Proof.Sort(groups, "sid name");
            return J.O("user_sid", creator ? Launcher.CREATOR_SID : TestSid, "token_type", 1UL, "elevated", creator, "elevation_type", creator ? 2UL : 1UL,
                "administrators_present", creator, "administrators_enabled", creator, "administrators_deny_only", false, "thread_token_absent", true,
                "groups", groups, "privileges", J.A(Privilege("SeChangeNotifyPrivilege", 3)));
        }
        private sealed class ReadFake : IReadAdapter
        {
            internal uint Point = 2221; internal int Index, Released;
            internal List<EnumPage> Pages = new List<EnumPage>();
            internal ReadFake() { Page(0, 0, "Other"); }
            internal void Page(uint status, uint resume, params string[] names)
            { Pages.Add(new EnumPage(status, (uint)names.Length, 999, resume, names.ToList(), delegate { Released++; })); }
            public uint AbsenceStatus() { return Point; }
            public EnumPage UsersPage(uint resume) { return Pages[Index++]; }
            public Dictionary<string, object> Token() { return GeneratedTests.Token(true); }
            public Dictionary<string, object> Account() { return GeneratedTests.Account(); }
            public Dictionary<string, object> UsersIdentity() { return Identity(); }
            public Dictionary<string, object> Groups(uint flags) { return View(flags, Launcher.BUILTIN_USERS_SID); }
        }
        private static Dictionary<string, object> Preflight()
        {
            return J.O("creator_token", Token(true), "absence", Proof.Absence(new ReadFake()), "root_absent", true,
                "root_identity", RootIdentity(),
                "tools", J.O("powershell_version", "5.1.TEST", "helper_source_commit", TestCommit, "helper_source_tree", TestTree,
                    "helper_sha256", TestHelperHash, "netapi32_version", "TEST_ONLY"), "users_identity", Identity(), "baseline_mode", "CONDITIONAL_USERS");
        }
        private static Dictionary<string, object> RootIdentity()
        {
            var root = SecurityProof.Decode(SecurityProof.CreateDescriptor());
            root.Add("volume_guid", RootProof.VolumeGuid); root.Add("volume_serial", RootProof.VolumeSerial);
            root.Add("file_id", "0000000000000042"); root.Add("resolved_final_path", RootProof.FinalPath); root.Add("reparse_point", false);
            return root;
        }
        private static byte[] Descriptor(RawSecurityDescriptor descriptor)
        { byte[] bytes = new byte[descriptor.BinaryLength]; descriptor.GetBinaryForm(bytes, 0); return bytes; }
        private static RawSecurityDescriptor RootDescriptor()
        { return new RawSecurityDescriptor(SecurityProof.CreateDescriptor(), 0); }
        private static byte[] ParentDescriptor(string sid, uint mask, AceFlags flags)
        {
            var descriptor = RootDescriptor();
            descriptor.DiscretionaryAcl.InsertAce(2, new CommonAce(flags, AceQualifier.AccessAllowed, unchecked((int)mask), new SecurityIdentifier(sid), false, null));
            return Descriptor(descriptor);
        }
        private static void RejectCode(Action action, string code, bool effect)
        {
            try { action(); }
            catch (CeremonyException ex) { Check(ex.Code == code && ex.EffectMayHaveOccurred == effect); return; }
            throw new Exception("EXPECTED_REJECTION");
        }
        private static Dictionary<string, object> CreationAttempt()
        { return J.O("absence", Proof.Absence(new ReadFake()), "creator_token", Token(true), "secure_input_method", "READ_HOST_SECURESTRING_GLOBALALLOCUNICODE",
            "creation_surface", "NETAPI32_NETUSERADD_LEVEL1", "options", Proof.Options()); }
        private static Dictionary<string, object> Created()
        { return J.O("net_status", 0UL, "creation_return_confirmed", true, "password_buffer_zero_freed", true, "securestring_disposed", true); }
        private static Dictionary<string, object> UsersAttempt()
        { return J.O("group_sid", Launcher.BUILTIN_USERS_SID, "member_sid", TestSid, "creator_token", Token(true), "direct_view", View(0), "users_identity", Identity()); }
        private static Dictionary<string, object> UsersConfirmed()
        { return J.O("group_sid", Launcher.BUILTIN_USERS_SID, "member_sid", TestSid, "net_status", 0UL, "direct_view", View(0, Launcher.BUILTIN_USERS_SID), "identity_continuity_passed", true); }
        private static Dictionary<string, object> Observation(bool performance)
        {
            var token = Token(false); var tg = J.Arr(token["groups"]);
            if (performance) tg.Add(TokenGroup(Launcher.PERFORMANCE_LOG_USERS_SID, 7)); Proof.Sort(tg, "sid name");
            var edges = J.A(J.O("member_sid", TestSid, "group_sid", Launcher.BUILTIN_USERS_SID, "origin", "DIRECT"),
                J.O("member_sid", Gate.Interactive, "group_sid", Launcher.PERFORMANCE_LOG_USERS_SID, "origin", "LOGON_CONTEXT")); Proof.Sort(edges, "member_sid group_sid origin");
            var effective = J.A();
            foreach (object v in tg) { var g = J.Obj(v); effective.Add(J.O("sid", g["sid"], "name", g["name"], "attributes", g["attributes"],
                "origin", J.S(g["sid"]) == Launcher.BUILTIN_USERS_SID ? "DIRECT" : "LOGON_CONTEXT", "disposition", "ACCEPTED")); }
            return J.O("account", Account(), "direct_view", View(0, Launcher.BUILTIN_USERS_SID), "indirect_view", View(1, Launcher.BUILTIN_USERS_SID),
                "relevant_edges", edges, "effective_groups", effective, "rights", J.A(), "candidate_token", token, "collection_method", "operator_observed_console",
                "performance_log_users", J.O("classification", Gate.PerformanceClass, "effective", performance, "direct_assignment", false,
                    "interactive_enabled", true, "host_edge_present", true, "alternate_path_present", false, "provenance_passed", true));
        }
        private static void Append(List<byte[]> chain, string ev, Dictionary<string, object> facts)
        { chain.Add(Evidence.Make(chain, ev, facts, Host(), "2026-09-02T00:00:00.0000000Z", "PASS", null)); }
        private static List<byte[]> Prefix(bool addUsers)
        {
            var c = new List<byte[]>(); Append(c, "PREFLIGHT", Preflight()); Append(c, "ACCOUNT_CREATION_ATTEMPTED", CreationAttempt());
            Append(c, "ACCOUNT_CREATED", Created()); Append(c, "ACCOUNT_SID_READ_BACK", J.O("account", Account()));
            Append(c, "USERS_BASELINE_SELECTED", J.O("branch", addUsers ? "ADD_USERS" : "ALREADY_USERS", "direct_view", addUsers ? View(0) : View(0, Launcher.BUILTIN_USERS_SID), "users_identity", Identity()));
            return c;
        }
        private static List<byte[]> Complete(bool addUsers)
        {
            var c = Prefix(addUsers); if (addUsers) { Append(c, "USERS_ASSIGNMENT_ATTEMPTED", UsersAttempt()); Append(c, "USERS_ASSIGNMENT_CONFIRMED", UsersConfirmed()); }
            Append(c, "QUALIFICATION_OBSERVED", Observation(true)); string hash = J.Hash(c.Last());
            Append(c, "GROUPS_QUALIFIED", J.O("observation_sha256", hash, "direct_baseline_passed", true, "indirect_review_passed", true, "special_authority_review_passed", true, "privileges_review_passed", true));
            Append(c, "TOKEN_QUALIFIED", J.O("observation_sha256", hash, "token_gate_passed", true, "enabled_recheck_passed", true, "identity_continuity_passed", true)); return c;
        }
        private sealed class MemoryStore : IStore
        {
            internal List<byte[]> Records = new List<byte[]>(); internal int Writes, FailAt; internal bool WrongReload;
            public List<byte[]> Load() { return WrongReload ? new List<byte[]>() : Records.Select(b => b.ToArray()).ToList(); }
            public void Publish(byte[] record) { Writes++; if (Writes == FailAt) throw new IOException("FAKE_RETENTION"); Records.Add(record.ToArray()); }
        }
        private sealed class FakeEffects : ITestEffects
        {
            internal int Creates, Adds; internal uint Status;
            public uint Create() { Creates++; return Status; }
            public uint AddUsers() { Adds++; return Status; }
        }
        // A generated temporary publisher exercises the strict loader contract.
        // It has no route to FixedStore or either native effect API.
        private sealed class TestFiles : IStore, IRecordFiles
        {
            private readonly string root;
            internal TestFiles(string testRoot) { root = testRoot; Directory.CreateDirectory(root); }
            public List<byte[]> Load()
            { return new RecordArchive(this).Load(); }
            public void Publish(byte[] b)
            { new RecordArchive(this).Publish(b); }
            public string[] Names() { return Directory.GetFileSystemEntries(root).Select(Path.GetFileName).ToArray(); }
            public byte[] Read(string name) { return File.ReadAllBytes(Path.Combine(root, name)); }
            public void CreateNew(string name, byte[] b)
            {
                using (var f = new FileStream(Path.Combine(root, name), FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
                { f.Write(b, 0, b.Length); f.Flush(true); }
            }
        }
        public static string Run(string temporaryRoot)
        {
            var tests = new Dictionary<string, Action>();
            tests.Add("fixed_identities", delegate {
                Check(Launcher.HOST == "DESKTOP-I4DOKM7" && Launcher.CANDIDATE_NAME == "P3R1KspTestUser");
                Check(Launcher.CREATOR_SID == Gate.MachineSid + "-1005" && Launcher.TRADING_SID == Gate.MachineSid + "-1009");
                Check(Launcher.BUILTIN_USERS_SID == "S-1-5-32-545" && Launcher.PERFORMANCE_LOG_USERS_SID == "S-1-5-32-559");
                Check(Launcher.CEREMONY_EVIDENCE_ROOT == @"F:\p3-r1-ordinary-nonadmin-principal-v2" && Launcher.KSP_EVIDENCE_ROOT == @"F:\AI\p3-r1-ksp-disposable-test-v1");
                Check(Gate.Schema == "p3-r1-ordinary-nonadmin-principal-evidence/v2");
            });
            tests.Add("real_gates", delegate {
                Reject(Launcher.RunFutureCeremony); Reject(delegate { new WindowsAdapter(); }); Reject(delegate { new FixedStore(); });
                RejectCode(delegate { new DirectoryGuard(RootProof.ParentPath); }, "SOURCE_DISABLED", false);
                RejectCode(delegate { SecurityProof.Read(IntPtr.Zero, false, false); }, "SOURCE_DISABLED", false);
                RejectCode(delegate { RootProof.NativeVolume(IntPtr.Zero, 0, RootProof.FinalPath); }, "SOURCE_DISABLED", false);
                Check(!Launcher.ACCOUNT_EFFECT_EXECUTION_AUTHORIZED && Launcher.Describe().Contains("candidate_sid=UNKNOWN"));
                Check(typeof(WindowsAdapter).GetInterfaces().All(x => x != typeof(ITestEffects)));
            });
            tests.Add("absence_complete", delegate {
                var f = new ReadFake(); f.Pages.Clear(); f.Page(234, 8, "Alice"); f.Page(234, 9); f.Page(0, 0, "Bob");
                var a = Proof.Absence(f); Check(f.Index == 3 && f.Released == 3 && J.Arr(a["enum_pages"]).Count == 3);
            });
            tests.Add("absence_statuses", delegate {
                foreach (uint status in new uint[] { 0, 5, 87, 234, 2224, UInt32.MaxValue })
                { var f = new ReadFake { Point = status }; Reject(delegate { Proof.Absence(f); }); Check(f.Index == 0); }
            });
            tests.Add("absence_collision", delegate {
                foreach (string name in new[] { Launcher.CANDIDATE_NAME, "p3r1ksptestuser", "P3R1KSPTESTUSER" })
                { var f = new ReadFake(); f.Pages.Clear(); f.Page(0, 0, name); Reject(delegate { Proof.Absence(f); }); Check(f.Released == 1); }
            });
            tests.Add("absence_duplicates_malformed", delegate {
                foreach (string[] names in new[] { new[] { "Alice", "ALICE" }, new[] { "" }, new[] { "bad\0name" }, new[] { "bad\\name" }, new[] { " spaced" } })
                { var f = new ReadFake(); f.Pages.Clear(); f.Page(0, 0, names); Reject(delegate { Proof.Absence(f); }); Check(f.Released == 1); }
                var wrong = new ReadFake(); wrong.Pages[0].Entries = 9; Reject(delegate { Proof.Absence(wrong); }); Check(wrong.Released == 1);
            });
            tests.Add("absence_resume_loops", delegate {
                var stalled = new ReadFake(); stalled.Pages.Clear(); stalled.Page(234, 0); Reject(delegate { Proof.Absence(stalled); }); Check(stalled.Released == 1);
                var cycle = new ReadFake(); cycle.Pages.Clear(); cycle.Page(234, 1); cycle.Page(234, 2); cycle.Page(234, 1);
                Reject(delegate { Proof.Absence(cycle); }); Check(cycle.Released == 3);
            });
            tests.Add("absence_terminal_error", delegate {
                var f = new ReadFake(); f.Pages.Clear(); f.Page(234, 1); f.Page(5, 2); Reject(delegate { Proof.Absence(f); }); Check(f.Released == 2);
                var truncated = new ReadFake(); truncated.Pages.Clear(); truncated.Page(234, 1); Reject(delegate { Proof.Absence(truncated); }); Check(truncated.Released == 1);
            });
            tests.Add("buffer_release_once", delegate {
                int freed = 0; var owned = new Owned(new IntPtr(7), 0, delegate { freed++; throw new IOException(); });
                Reject(owned.Dispose); owned.Dispose(); Check(freed == 1 && owned.Pointer == IntPtr.Zero);
                int pageFreed = 0; var page = new EnumPage(0, 0, 0, 0, new List<string>(), delegate { pageFreed++; throw new IOException(); });
                Reject(page.Dispose); page.Dispose(); Check(pageFreed == 1);
            });
            tests.Add("buffer_bounds", delegate {
                using (var b = Owned.Allocate(16)) {
                    b.Range(b.Pointer, 16); Reject(delegate { b.Range(IntPtr.Add(b.Pointer, 15), 2); });
                    Reject(delegate { b.Range(IntPtr.Add(b.Pointer, -1), 1); }); Reject(delegate { b.Structure<Native.USER_INFO_2>(b.Pointer); });
                    for (int i = 0; i < 16; i++) Marshal.WriteByte(b.Pointer, i, 65);
                    Reject(delegate { b.Text(b.Pointer, false); }); Reject(delegate { b.Text(IntPtr.Zero, false); });
                }
            });
            tests.Add("frozen_user_and_status", delegate {
                var u = WindowsAdapter.FrozenUser(new IntPtr(42));
                Check(u.name == Launcher.CANDIDATE_NAME && u.password == new IntPtr(42) && u.privilege == 1 && u.flags == 1 && u.password_age == 0);
                Check(u.home_dir == null && u.script_path == null && u.comment == Gate.Comment);
                Check(Proof.CreateStatus(0) == "CONFIRMED" && Proof.CreateStatus(2224) == "COLLISION");
                foreach (uint s in new uint[] { 5, 87, 2221, 2245, UInt32.MaxValue }) Check(Proof.CreateStatus(s) == "UNCERTAIN");
            });
            tests.Add("account_validation", delegate {
                Proof.Account(Account());
                foreach (var pair in J.O("sid", Launcher.CREATOR_SID, "name", "p3r1ksptestuser", "enabled", false, "privilege", 2UL, "flags", 515UL,
                    "comment", "changed", "full_name", "extra", "account_expires", 0UL, "machine_domain_sid", "S-1-5-21-1-2-3", "bidirectional_mapping_passed", false))
                { var a = Account(); a[pair.Key] = pair.Value; Reject(delegate { Proof.Account(a); }); }
                foreach (string sid in new[] { Launcher.TRADING_SID, "s-1-5-21-1-2-3-4", "S-1-05-21-1-2-3-4", Gate.MachineSid + "-042", Gate.MachineSid + "-4294967296" })
                    Reject(delegate { J.CandidateSid(sid); });
            });
            tests.Add("group_views_and_branches", delegate {
                Check(Proof.Branch(View(0)) == "ADD_USERS" && Proof.Branch(View(0, Launcher.BUILTIN_USERS_SID)) == "ALREADY_USERS");
                Reject(delegate { Proof.Branch(View(1, Launcher.BUILTIN_USERS_SID)); });
                Reject(delegate { Proof.Branch(View(0, Launcher.BUILTIN_USERS_SID, Gate.Administrators)); });
                var more = View(0); more["status"] = 234UL; Reject(delegate { Proof.Branch(more); });
                var count = View(1); count["total_entries"] = 2UL; Reject(delegate { Proof.Groups(count, 1); });
                var duplicate = View(0, Launcher.BUILTIN_USERS_SID); J.Arr(duplicate["groups"]).Add(Group(Launcher.BUILTIN_USERS_SID));
                duplicate["entries_read"] = duplicate["total_entries"] = 2UL; Reject(delegate { Proof.Groups(duplicate, 0); });
            });
            tests.Add("token_validation", delegate {
                Proof.Creator(Token(true)); Proof.Ordinary(Token(false), TestSid);
                foreach (var pair in J.O("user_sid", Launcher.TRADING_SID, "token_type", 2UL, "elevated", true, "elevation_type", 2UL, "thread_token_absent", false))
                { var t = Token(false); t[pair.Key] = pair.Value; Reject(delegate { Proof.Ordinary(t, TestSid); }); }
                foreach (ulong attributes in new ulong[] { 0, 7, 16 }) {
                    var t = Token(false); J.Arr(t["groups"]).Add(TokenGroup(Gate.Administrators, attributes)); Proof.Sort(J.Arr(t["groups"]), "sid name");
                    t["administrators_present"] = true; t["administrators_enabled"] = (attributes & 4) != 0; t["administrators_deny_only"] = (attributes & 16) != 0;
                    Reject(delegate { Proof.Ordinary(t, TestSid); });
                }
            });
            tests.Add("privileges", delegate {
                foreach (string name in new[] { "SeDebugPrivilege", "SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege", "SeSecurityPrivilege",
                    "SeTcbPrivilege", "SeCreateTokenPrivilege", "SeAssignPrimaryTokenPrivilege", "SeImpersonatePrivilege", "SeLoadDriverPrivilege", "SeRelabelPrivilege", "SeUnknownPrivilege" })
                foreach (ulong attributes in new ulong[] { 0, 2, 4 }) {
                    var t = Token(false); t["privileges"] = J.A(Privilege(name, attributes)); Reject(delegate { Proof.Ordinary(t, TestSid); });
                }
                foreach (ulong a in new ulong[] { 0, 2, 3, 0x80000003 }) { var t = Token(false); t["privileges"] = J.A(Privilege("SeChangeNotifyPrivilege", a)); Proof.Ordinary(t, TestSid); }
                foreach (string name in new[] { "SeShutdownPrivilege", "SeUndockPrivilege", "SeIncreaseWorkingSetPrivilege", "SeTimeZonePrivilege" }) {
                    var t = Token(false); t["privileges"] = J.A(Privilege(name, 0)); Proof.Ordinary(t, TestSid);
                }
                var bad = Token(false); J.Obj(J.Arr(bad["privileges"])[0])["enabled"] = false; Reject(delegate { Proof.Ordinary(bad, TestSid); });
                var right = Observation(false); right["rights"] = J.A(J.O("principal_sid", TestSid, "name", "SeServiceLogonRight", "origin", "DIRECT", "disposition", "UNRESOLVED"));
                Reject(delegate { Qualification.Accept(right); });
            });
            tests.Add("performance_provenance", delegate {
                Qualification.Accept(Observation(true)); Qualification.Accept(Observation(false));
                foreach (string key in new[] { "direct_assignment", "interactive_enabled", "host_edge_present", "alternate_path_present", "provenance_passed" }) {
                    var o = Observation(true); var p = J.Obj(o["performance_log_users"]); p[key] = !J.B(p[key]); Reject(delegate { Qualification.Accept(o); });
                }
                var missing = Observation(true); J.Arr(missing["relevant_edges"]).RemoveAt(1); J.Obj(missing["performance_log_users"])["host_edge_present"] = false;
                Reject(delegate { Qualification.Accept(missing); });
                var direct = Observation(true); direct["direct_view"] = View(0, Launcher.BUILTIN_USERS_SID, Launcher.PERFORMANCE_LOG_USERS_SID); Reject(delegate { Qualification.Accept(direct); });
            });
            tests.Add("graph_cycle_and_alternate", delegate {
                var cycle = J.A(J.O("member_sid", "S-1-5-4", "group_sid", "S-1-5-11", "origin", "NESTED"), J.O("member_sid", "S-1-5-11", "group_sid", "S-1-5-4", "origin", "NESTED"));
                Reject(delegate { Qualification.Reach(new[] { "S-1-5-4" }, cycle, false); });
                var o = Observation(true); J.Arr(o["relevant_edges"]).Add(J.O("member_sid", Launcher.BUILTIN_USERS_SID, "group_sid", Launcher.PERFORMANCE_LOG_USERS_SID, "origin", "NESTED"));
                Proof.Sort(J.Arr(o["relevant_edges"]), "member_sid group_sid origin"); Reject(delegate { Qualification.Accept(o); });
            });
            tests.Add("strict_json", delegate {
                foreach (string text in new[] { "{}\n", " { }", "{\"a\":1,\"a\":1}", "{\"a\":01}", "{\"a\":-0}", "{\"a\":1.0}", "{\"a\":1e0}", "{\"a\":18446744073709551616}", "{\"a\":\"\\ud800\"}", "{\"z\":0,\"a\":0}", "\ufeff{}" })
                    Reject(delegate { J.Parse(Encoding.UTF8.GetBytes(text)); });
                var value = J.O("z", "\n\u0001\"\\", "a", "\u00e9\ud83d\ude00"); Check(J.Bytes(J.Parse(J.Bytes(value))).SequenceEqual(J.Bytes(value)));
                Reject(delegate { J.Bytes(new object()); }); Reject(delegate { J.Bytes(1.5); });
            });
            tests.Add("evidence_roundtrip", delegate {
                foreach (bool add in new[] { false, true }) { var c = Complete(add); Evidence.Validate(c); Check(Evidence.Next(c) == null); foreach (byte[] b in c) Check(J.Bytes(J.Parse(b)).SequenceEqual(b)); }
            });
            tests.Add("evidence_fields", delegate {
                var c = Prefix(false); var original = J.Obj(J.Parse(c[0]));
                foreach (string key in original.Keys) { var r = J.Obj(J.Clone(original)); r.Remove(key); Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(r) }); }); }
                var extra = J.Obj(J.Clone(original)); extra.Add("password", "FORBIDDEN_TEST_FIELD"); Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(extra) }); });
                var nested = J.Obj(J.Clone(original)); J.Obj(J.Obj(nested["facts"])["creator_token"]).Add("native_handle", 0UL); Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(nested) }); });
                string text = Encoding.UTF8.GetString(c[0]); string duplicated = text.Replace("\"schema\":", "\"schema\":\"duplicate\",\"schema\":"); Reject(delegate { J.Parse(Encoding.UTF8.GetBytes(duplicated)); });
            });
            tests.Add("evidence_order_hash_lifecycle", delegate {
                var c = Complete(true); var gap = c.ToList(); gap.RemoveAt(2); Reject(delegate { Evidence.Validate(gap); });
                var duplicate = c.ToList(); duplicate.Insert(2, c[1]); Reject(delegate { Evidence.Validate(duplicate); });
                foreach (string key in new[] { "sequence", "previous_sha256", "event" }) {
                    var copy = c.ToList(); var r = J.Obj(J.Parse(copy[2])); r[key] = key == "sequence" ? (object)9UL : key == "event" ? "PREFLIGHT" : new string('a', 64);
                    copy[2] = J.Bytes(r); Reject(delegate { Evidence.Validate(copy); });
                }
                var regression = c.ToList(); var last = J.Obj(J.Parse(regression.Last())); J.Obj(last["lifecycle"])["ACCOUNT_CREATED"] = false; regression[regression.Count - 1] = J.Bytes(last);
                Reject(delegate { Evidence.Validate(regression); });
            });
            tests.Add("evidence_sid_drift", delegate {
                var c = Prefix(false); var o = Observation(false); J.Obj(o["account"])["sid"] = Gate.MachineSid + "-424243";
                Reject(delegate { Append(c, "QUALIFICATION_OBSERVED", o); });
                var wrong = Prefix(true); var attempt = UsersAttempt(); attempt["member_sid"] = Launcher.TRADING_SID; Reject(delegate { Append(wrong, "USERS_ASSIGNMENT_ATTEMPTED", attempt); });
            });
            tests.Add("stop_terminality", delegate {
                var store = new MemoryStore(); var j = new Journal(store, Host()); j.Advance("PREFLIGHT", Preflight());
                j.Stop("PREFLIGHT", "GATE_REJECTED", "NONE", null, null); Evidence.Validate(j.Confirmed); Check(Evidence.Next(j.Confirmed) == null);
                Reject(delegate { j.Advance("ACCOUNT_CREATION_ATTEMPTED", CreationAttempt()); });
                var c = j.Confirmed; Reject(delegate { Append(c, "ACCOUNT_CREATION_ATTEMPTED", CreationAttempt()); });
            });
            tests.Add("create_pre_retention_failure", delegate {
                var store = new MemoryStore(); var j = new Journal(store, Host()); j.Advance("PREFLIGHT", Preflight()); store.FailAt = 2;
                var fake = new FakeEffects(); var runner = new TestEffectRunner(j, fake);
                Reject(delegate { runner.Execute("ACCOUNT_CREATION_ATTEMPTED", CreationAttempt(), "ACCOUNT_CREATED", Created()); });
                Check(fake.Creates == 0 && fake.Adds == 0 && j.Halted && j.Confirmed.Count == 1 && !j.EffectMayHaveOccurred);
            });
            tests.Add("users_pre_retention_failure", delegate {
                var store = new MemoryStore { Records = Prefix(true), FailAt = 1 }; var j = new Journal(store, Host()); var fake = new FakeEffects(); var runner = new TestEffectRunner(j, fake);
                Reject(delegate { runner.Execute("USERS_ASSIGNMENT_ATTEMPTED", UsersAttempt(), "USERS_ASSIGNMENT_CONFIRMED", UsersConfirmed()); });
                Check(fake.Adds == 0 && fake.Creates == 0 && j.Halted && j.Confirmed.Count == 5);
            });
            tests.Add("post_effect_retention_failure", delegate {
                foreach (bool users in new[] { false, true }) {
                    var store = new MemoryStore { Records = users ? Prefix(true) : Prefix(false).Take(1).ToList(), FailAt = 2 };
                    var j = new Journal(store, Host()); var fake = new FakeEffects(); var runner = new TestEffectRunner(j, fake);
                    string attempted = users ? "USERS_ASSIGNMENT_ATTEMPTED" : "ACCOUNT_CREATION_ATTEMPTED", confirmed = users ? "USERS_ASSIGNMENT_CONFIRMED" : "ACCOUNT_CREATED";
                    var before = users ? UsersAttempt() : CreationAttempt(); var after = users ? UsersConfirmed() : Created();
                    Reject(delegate { runner.Execute(attempted, before, confirmed, after); }); Check(j.Halted && j.EffectMayHaveOccurred && store.Writes == 2 && fake.Creates + fake.Adds == 1);
                    Reject(delegate { runner.Execute(attempted, before, confirmed, after); });
                    var second = new TestEffectRunner(j, fake); Reject(delegate { second.Execute(attempted, before, confirmed, after); }); Check(fake.Creates + fake.Adds == 1 && store.Writes == 2);
                    var reopened = new Journal(store, Host()); Reject(delegate { reopened.BeginDispatch(attempted); });
                }
            });
            tests.Add("reload_mismatch", delegate {
                var store = new MemoryStore(); var j = new Journal(store, Host()); j.Advance("PREFLIGHT", Preflight()); store.WrongReload = true;
                var fake = new FakeEffects(); var runner = new TestEffectRunner(j, fake);
                Reject(delegate { runner.Execute("ACCOUNT_CREATION_ATTEMPTED", CreationAttempt(), "ACCOUNT_CREATED", Created()); }); Check(fake.Creates == 0 && j.Halted);
            });
            tests.Add("fake_success_branches", delegate {
                foreach (bool users in new[] { false, true }) {
                    var store = new MemoryStore { Records = users ? Prefix(true) : Prefix(false).Take(1).ToList() }; var j = new Journal(store, Host()); var fake = new FakeEffects();
                    new TestEffectRunner(j, fake).Execute(users ? "USERS_ASSIGNMENT_ATTEMPTED" : "ACCOUNT_CREATION_ATTEMPTED", users ? UsersAttempt() : CreationAttempt(),
                        users ? "USERS_ASSIGNMENT_CONFIRMED" : "ACCOUNT_CREATED", users ? UsersConfirmed() : Created()); Check(fake.Creates + fake.Adds == 1); Evidence.Validate(j.Confirmed);
                }
                var bad = new MemoryStore { Records = Prefix(false).Take(1).ToList() }; var state = new Journal(bad, Host()); var failing = new FakeEffects { Status = 2224 };
                Reject(delegate { new TestEffectRunner(state, failing).Execute("ACCOUNT_CREATION_ATTEMPTED", CreationAttempt(), "ACCOUNT_CREATED", Created()); }); Check(state.Halted && failing.Creates == 1);
            });
            tests.Add("test_store_no_overwrite_unknown_gaps", delegate {
                string path = Path.Combine(temporaryRoot, "records"); var files = new TestFiles(path); var j = new Journal(files, Host()); j.Advance("PREFLIGHT", Preflight());
                Reject(delegate { files.Publish(j.Confirmed[0]); }); Check(files.Load().Count == 1);
                File.WriteAllText(Path.Combine(path, "unknown.json"), "{}"); Reject(delegate { files.Load(); });
                string gap = Path.Combine(temporaryRoot, "gap"); Directory.CreateDirectory(gap); File.WriteAllBytes(Path.Combine(gap, "record-002.json"), j.Confirmed[0]); Reject(delegate { new TestFiles(gap).Load(); });
            });
            tests.Add("protected_root_descriptor", delegate {
                byte[] bytes = SecurityProof.CreateDescriptor(); var decoded = SecurityProof.Decode(bytes);
                SecurityProof.Protected(decoded, false); Check(J.S(decoded["owner_sid"]) == Launcher.CREATOR_SID && decoded["group_sid"] == null);
                var native = new RawSecurityDescriptor(bytes, 0);
                Check((native.ControlFlags & ControlFlags.DiscretionaryAclProtected) != 0 && native.DiscretionaryAcl.Count == 2);
                Check(native.DiscretionaryAcl[0].AceFlags == (AceFlags.ObjectInherit | AceFlags.ContainerInherit));
                Check(((CommonAce)native.DiscretionaryAcl[0]).SecurityIdentifier.Value == "S-1-5-18");
                Check(((CommonAce)native.DiscretionaryAcl[1]).SecurityIdentifier.Value == Gate.Administrators);
                Check(((CommonAce)native.DiscretionaryAcl[0]).AccessMask == 0x001F01FF);
                native.Group = new SecurityIdentifier(Launcher.BUILTIN_USERS_SID);
                var grouped = SecurityProof.Decode(Descriptor(native)); SecurityProof.Protected(grouped, false);
                Check(J.S(grouped["group_sid"]) == Launcher.BUILTIN_USERS_SID); // observed, never writer authority
                // Equivalent SDDL spelling/binary layout is not textual authority.
                var equivalent = new RawSecurityDescriptor("O:" + Launcher.CREATOR_SID + "D:P(A;OICI;0x1f01ff;;;S-1-5-18)(A;OICI;FA;;;S-1-5-32-544)");
                Check(J.Bytes(decoded).SequenceEqual(J.Bytes(SecurityProof.Decode(Descriptor(equivalent)))));
                RootProof.Identity(RootIdentity());
            });
            tests.Add("protected_root_inheritance", delegate {
                var descriptor = RootDescriptor();
                descriptor.SetFlags(ControlFlags.SelfRelative | ControlFlags.DiscretionaryAclPresent | ControlFlags.DiscretionaryAclAutoInherited);
                foreach (GenericAce ace in descriptor.DiscretionaryAcl) ace.AceFlags = AceFlags.Inherited;
                SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), true);
                Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), false); });
                foreach (AceFlags flags in new[] { AceFlags.None, AceFlags.InheritOnly, AceFlags.Inherited | AceFlags.ObjectInherit }) {
                    descriptor.DiscretionaryAcl[0].AceFlags = flags;
                    Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), true); });
                }
                descriptor.DiscretionaryAcl[0].AceFlags = AceFlags.Inherited;
                descriptor.Owner = new SecurityIdentifier(TestSid);
                Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), true); });
                descriptor.Owner = new SecurityIdentifier(Launcher.CREATOR_SID);
                descriptor.DiscretionaryAcl.InsertAce(2, new CommonAce(AceFlags.Inherited, AceQualifier.AccessAllowed, 1, new SecurityIdentifier(TestSid), false, null));
                Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), true); });
            });
            tests.Add("malformed_security_descriptors", delegate {
                byte[] valid = SecurityProof.CreateDescriptor();
                foreach (int size in new[] { 0, 1, 19, valid.Length - 1 }) {
                    byte[] truncated = valid.Take(size).ToArray(); Reject(delegate { SecurityProof.Decode(truncated); });
                }
                Reject(delegate { SecurityProof.Decode(null); });
                foreach (int offset in new[] { 0, 1, 4, 8, 12, 16 }) {
                    byte[] bad = valid.ToArray(); bad[offset] = 255; Reject(delegate { SecurityProof.Decode(bad); });
                }
                int acl = BitConverter.ToInt32(valid, 16), owner = BitConverter.ToInt32(valid, 4);
                foreach (int offset in new[] { owner, owner + 1, acl, acl + 1, acl + 2, acl + 4, acl + 6, acl + 8, acl + 9, acl + 10, acl + 16 }) {
                    byte[] bad = valid.ToArray(); bad[offset] = 255; Reject(delegate { SecurityProof.Decode(bad); });
                }
                byte[] overlap = valid.ToArray(); Array.Copy(BitConverter.GetBytes(acl + 8), 0, overlap, 4, 4);
                Reject(delegate { SecurityProof.Decode(overlap); });
                var callback = RootDescriptor(); callback.DiscretionaryAcl.InsertAce(2, new CommonAce(AceFlags.None, AceQualifier.AccessAllowed,
                    1, new SecurityIdentifier(TestSid), true, new byte[4]));
                Reject(delegate { SecurityProof.Decode(Descriptor(callback)); });
                var nullAcl = RootDescriptor(); nullAcl.DiscretionaryAcl = null;
                Reject(delegate { SecurityProof.Decode(Descriptor(nullAcl)); });
                var nullOwner = RootDescriptor(); nullOwner.Owner = null;
                Reject(delegate { SecurityProof.Decode(Descriptor(nullOwner)); });
                var group = RootDescriptor(); group.Group = new SecurityIdentifier(TestSid); byte[] invalidGroup = Descriptor(group);
                invalidGroup[BitConverter.ToInt32(invalidGroup, 8) + 1] = 255;
                Reject(delegate { SecurityProof.Decode(invalidGroup); });
            });
            tests.Add("wrong_root_owner", delegate {
                foreach (string sid in new[] { Gate.Administrators, "S-1-5-18", TestSid, Launcher.TRADING_SID }) {
                    var descriptor = RootDescriptor(); descriptor.Owner = new SecurityIdentifier(sid);
                    Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), false); });
                }
            });
            tests.Add("removed_dacl_protection", delegate {
                var descriptor = RootDescriptor(); descriptor.SetFlags(descriptor.ControlFlags & ~ControlFlags.DiscretionaryAclProtected);
                Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), false); });
                byte[] noPresent = SecurityProof.CreateDescriptor(); noPresent[2] = (byte)(noPresent[2] & ~4);
                Reject(delegate { SecurityProof.Decode(noPresent); });
            });
            tests.Add("extra_untrusted_root_ace", delegate {
                foreach (string sid in new[] { TestSid, Launcher.TRADING_SID, Launcher.BUILTIN_USERS_SID, "S-1-5-11", Launcher.CREATOR_SID, Gate.Administrators })
                foreach (int mask in new[] { 1, (int)SecurityProof.FullControl }) {
                    var descriptor = RootDescriptor(); descriptor.DiscretionaryAcl.InsertAce(2, new CommonAce(AceFlags.ObjectInherit | AceFlags.ContainerInherit,
                        AceQualifier.AccessAllowed, mask, new SecurityIdentifier(sid), false, null));
                    Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), false); });
                }
                foreach (AceFlags flags in new[] { AceFlags.None, AceFlags.ObjectInherit, AceFlags.ContainerInherit,
                    AceFlags.ObjectInherit | AceFlags.ContainerInherit | AceFlags.InheritOnly,
                    AceFlags.ObjectInherit | AceFlags.ContainerInherit | AceFlags.NoPropagateInherit, AceFlags.Inherited }) {
                    var descriptor = RootDescriptor(); descriptor.DiscretionaryAcl[1].AceFlags = flags;
                    Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(descriptor)), false); });
                }
                var wrongMask = RootDescriptor(); ((CommonAce)wrongMask.DiscretionaryAcl[0]).AccessMask = 1;
                Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(wrongMask)), false); });
                var deny = RootDescriptor(); deny.DiscretionaryAcl.InsertAce(0, new CommonAce(AceFlags.None, AceQualifier.AccessDenied,
                    1, new SecurityIdentifier(TestSid), false, null));
                Reject(delegate { SecurityProof.Protected(SecurityProof.Decode(Descriptor(deny)), false); });
            });
            tests.Add("unsafe_parent_delete_child", delegate {
                foreach (string sid in new[] { TestSid, "S-1-5-11", "S-1-1-0", Launcher.BUILTIN_USERS_SID, Launcher.TRADING_SID })
                foreach (AceFlags flags in new[] { AceFlags.None, AceFlags.ObjectInherit | AceFlags.ContainerInherit, AceFlags.Inherited })
                    RejectCode(delegate { SecurityProof.Parent(ParentDescriptor(sid, 0x40, flags)); }, "UNTRUSTED_PARENT_REPLACEMENT", false);
            });
            tests.Add("unsafe_parent_security_authority", delegate {
                foreach (uint mask in new uint[] { 0x40000, 0x80000, 0xC0040, 0x10000000, SecurityProof.FullControl })
                    RejectCode(delegate { SecurityProof.Parent(ParentDescriptor(TestSid, mask, AceFlags.None)); }, "UNTRUSTED_PARENT_REPLACEMENT", false);
                var wrongOwner = RootDescriptor(); wrongOwner.Owner = new SecurityIdentifier(TestSid);
                RejectCode(delegate { SecurityProof.Parent(Descriptor(wrongOwner)); }, "PARENT_OWNER", false);
                // Denies are never used to excuse uncertain effective allows.
                var denied = new RawSecurityDescriptor(ParentDescriptor(TestSid, 0x40, AceFlags.None), 0);
                denied.DiscretionaryAcl.InsertAce(0, new CommonAce(AceFlags.None, AceQualifier.AccessDenied, 0x40, new SecurityIdentifier(TestSid), false, null));
                RejectCode(delegate { SecurityProof.Parent(Descriptor(denied)); }, "UNTRUSTED_PARENT_REPLACEMENT", false);
                foreach (uint mask in new uint[] { 0x02000000, 0x01000000, 0x200 })
                    Reject(delegate { SecurityProof.Parent(ParentDescriptor(TestSid, mask, AceFlags.None)); });
            });
            tests.Add("safe_parent_creation_and_read_rights", delegate {
                foreach (uint mask in new uint[] { 1, 2, 4, 0x20, 0x10000, 0x1201BF, 0x40000000, 0x80000000, 0x20000000 })
                    SecurityProof.Parent(ParentDescriptor(TestSid, mask, AceFlags.None));
                SecurityProof.Parent(ParentDescriptor(TestSid, SecurityProof.FullControl, AceFlags.ObjectInherit | AceFlags.ContainerInherit | AceFlags.InheritOnly));
                foreach (string sid in new[] { Launcher.CREATOR_SID, Gate.Administrators, "S-1-5-18" })
                    SecurityProof.Parent(ParentDescriptor(sid, SecurityProof.FullControl, AceFlags.None));
            });
            tests.Add("wrong_volume_identity", delegate {
                RootProof.Volume(3, "NTFS", 8, (uint)RootProof.VolumeSerial, RootProof.VolumeGuid, RootProof.VolumeGuid);
                foreach (uint drive in new uint[] { 0, 1, 2, 4, 5, 6 })
                    Reject(delegate { RootProof.Volume(drive, "NTFS", 8, (uint)RootProof.VolumeSerial, RootProof.VolumeGuid, RootProof.VolumeGuid); });
                Reject(delegate { RootProof.Volume(3, "ReFS", 8, (uint)RootProof.VolumeSerial, RootProof.VolumeGuid, RootProof.VolumeGuid); });
                Reject(delegate { RootProof.Volume(3, "NTFS", 0, (uint)RootProof.VolumeSerial, RootProof.VolumeGuid, RootProof.VolumeGuid); });
                Reject(delegate { RootProof.Volume(3, "NTFS", 8, 1, RootProof.VolumeGuid, RootProof.VolumeGuid); });
                foreach (string final in new[] { @"\\?\F:\", RootProof.VolumeGuid + "AI", @"\\?\Volume{00000000-0000-0000-0000-000000000000}\" })
                    Reject(delegate { RootProof.Volume(3, "NTFS", 8, (uint)RootProof.VolumeSerial, final, RootProof.VolumeGuid); });
            });
            tests.Add("wrong_root_file_identity", delegate {
                var frozen = RootIdentity(); var changed = RootIdentity(); changed["file_id"] = "0000000000000043";
                RejectCode(delegate { RootProof.Continuity(changed, frozen); }, "ROOT_IDENTITY_DRIFT", false);
                RootProof.Continuity(RootIdentity(), frozen);
                var files = new TestFiles(Path.Combine(temporaryRoot, "identity")); files.Publish(Prefix(false)[0]);
                RejectCode(delegate { RootProof.Retained(files.Load(), changed); }, "ROOT_IDENTITY_DRIFT", false);
            });
            tests.Add("root_reparse_substitution", delegate {
                RootProof.Directory(0x10);
                foreach (uint attr in new uint[] { 0, 0x400, 0x410, UInt32.MaxValue })
                    RejectCode(delegate { RootProof.Directory(attr); }, "DIRECTORY_REPARSE", false);
                var root = RootIdentity(); root["reparse_point"] = true; Reject(delegate { RootProof.Continuity(root, RootIdentity()); });
                root = RootIdentity(); root["resolved_final_path"] = RootProof.VolumeGuid + "moved";
                Reject(delegate { RootProof.Continuity(root, RootIdentity()); });
            });
            tests.Add("precreated_root_collision", delegate {
                RootProof.Absent(UInt32.MaxValue, 2);
                foreach (uint attr in new uint[] { 0, 0x10, 0x410 })
                    RejectCode(delegate { RootProof.Absent(attr, 0); }, "ROOT_COLLISION", false);
                foreach (int error in new[] { 0, 3, 5, 183 })
                    RejectCode(delegate { RootProof.Absent(UInt32.MaxValue, error); }, "ROOT_ABSENCE_UNKNOWN", false);
                var state = new RootCreationAttempt(); state.Begin(); RejectCode(delegate { state.Complete(false, 183); }, "ROOT_COLLISION", false);
                RejectCode(state.Begin, "ROOT_ATTEMPT_CONSUMED", false);
                var files = new TestFiles(Path.Combine(temporaryRoot, "precreated"));
                RejectCode(delegate { RootProof.Retained(files.Load(), RootIdentity()); }, "ROOT_COLLISION_OR_UNCONFIRMED", false);
                Check(files.Names().Length == 0);
            });
            tests.Add("uncertain_root_creation", delegate {
                foreach (int error in new[] { 0, 3, 5, 87, 112, Int32.MaxValue }) {
                    var state = new RootCreationAttempt(); state.Begin();
                    RejectCode(delegate { state.Complete(false, error); }, "ROOT_CREATE_UNCERTAIN", true);
                    RejectCode(state.Begin, "ROOT_ATTEMPT_CONSUMED", false);
                }
                var lostReturn = new RootCreationAttempt(); lostReturn.Begin(); RejectCode(lostReturn.Begin, "ROOT_ATTEMPT_CONSUMED", false);
                var success = new RootCreationAttempt(); success.Begin(); success.Complete(true, 183); // stale last-error is irrelevant on success
                RejectCode(success.Begin, "ROOT_ATTEMPT_CONSUMED", false);
                Reject(delegate { success.Complete(true, 0); });
            });
            tests.Add("strict_v2_root_reload", delegate {
                var files = new TestFiles(Path.Combine(temporaryRoot, "v2")); foreach (byte[] bytes in Complete(false)) files.Publish(bytes);
                var chain = files.Load(); RootProof.Retained(chain, RootIdentity());
                var record = J.Obj(J.Parse(chain[0])); var root = J.Obj(J.Obj(record["facts"])["root_identity"]);
                foreach (string key in root.Keys) {
                    var missing = J.Obj(J.Clone(record)); J.Obj(J.Obj(missing["facts"])["root_identity"]).Remove(key);
                    Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(missing) }); });
                }
                foreach (var pair in J.O("volume_guid", "wrong", "volume_serial", 1UL, "file_id", "0000000000000000", "owner_sid", Gate.Administrators,
                    "group_sid", "not-a-sid", "dacl_semantic_identity", J.A(), "dacl_protected", false, "reparse_point", true, "resolved_final_path", Launcher.CEREMONY_EVIDENCE_ROOT)) {
                    var changed = J.Obj(J.Clone(record)); J.Obj(J.Obj(changed["facts"])["root_identity"])[pair.Key] = pair.Value;
                    Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(changed) }); });
                }
                foreach (string extra in new[] { "dacl_sddl", "native_handle", "security_override" }) {
                    var changed = J.Obj(J.Clone(record)); J.Obj(J.Obj(changed["facts"])["root_identity"]).Add(extra, "FORBIDDEN");
                    Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(changed) }); });
                }
                var old = J.Obj(J.Clone(record)); old["schema"] = "p3-r1-ordinary-nonadmin-principal-evidence/v1";
                Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(old) }); });
                old = J.Obj(J.Clone(record)); J.Obj(old["ceremony"])["evidence_root"] = @"F:\AI\p3-r1-ordinary-nonadmin-principal-v1";
                Reject(delegate { Evidence.Validate(new List<byte[]> { J.Bytes(old) }); });
                // Re-entry can observe the retained chain, never re-dispatch an effect.
                var reopened = new Journal(files, Host()); Reject(delegate { reopened.BeginDispatch("ACCOUNT_CREATION_ATTEMPTED"); });
            });
            var results = J.O();
            foreach (var test in tests)
            {
                try { test.Value(); results.Add(test.Key, "PASS"); }
                catch (Exception ex) { results.Add(test.Key, ex.GetType().Name + ":" + ex.Message); }
            }
            return Encoding.UTF8.GetString(J.Bytes(results));
        }
    }
}
"""  # noqa: E501
