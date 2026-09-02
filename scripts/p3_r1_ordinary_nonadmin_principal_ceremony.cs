// Source-only implementation of the accepted P3-R1 ordinary-user ceremony.
// No account, group, evidence-root, password, logon, or KSP effect is authorized.
// Compile with the installed x64 Windows PowerShell 5.1 Add-Type compiler.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Management.Automation;
using System.Runtime.InteropServices;
using System.Security;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;

namespace P3R1OrdinaryPrincipalV1
{
    public static class Launcher
    {
        public const bool ACCOUNT_EFFECT_EXECUTION_AUTHORIZED = false;
        public const string ACCOUNT_EFFECT_AUTHORIZATION_ID = "NOT-AUTHORIZED-P3R1-ORDINARY-NONADMIN-PRINCIPAL-V1";
        public const string HOST = "DESKTOP-I4DOKM7";
        public const string CREATOR_SID = "S-1-5-21-1397534616-3988210162-180023805-1005";
        public const string TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009";
        public const string CANDIDATE_NAME = "P3R1KspTestUser";
        public const string BUILTIN_USERS_SID = "S-1-5-32-545";
        public const string PERFORMANCE_LOG_USERS_SID = "S-1-5-32-559";
        public const string CEREMONY_EVIDENCE_ROOT = @"F:\AI\p3-r1-ordinary-nonadmin-principal-v1";
        public const string KSP_EVIDENCE_ROOT = @"F:\AI\p3-r1-ksp-disposable-test-v1";

        public static string Describe()
        {
            return "SOURCE_ONLY; ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false; " +
                ACCOUNT_EFFECT_AUTHORIZATION_ID + "; candidate=" + CANDIDATE_NAME +
                "; host=" + HOST + "; candidate_sid=UNKNOWN; password_prompt=false; native_dispatch=false; evidence_root_creation=false";
        }

        // This is the only real runner. No caller evidence, identity, operation,
        // password argument, path, phase selection, or authorization is accepted.
        public static void RunFutureCeremony()
        {
            Gate.Require(); // BEFORE constructing an adapter, store, or prompt.
            using (WindowsAdapter native = new WindowsAdapter())
            using (FixedStore store = new FixedStore())
            {
                RealRunner.Run(native, store);
            }
        }
    }

    internal static class Gate
    {
        internal const string MachineSid = "S-1-5-21-1397534616-3988210162-180023805";
        internal const string Administrators = "S-1-5-32-544";
        internal const string Interactive = "S-1-5-4";
        internal const string Comment = "P3-R1 ordinary non-admin test only";
        internal const string Schema = "p3-r1-ordinary-nonadmin-principal-evidence/v1";
        internal const string PerformanceClass = "CONDITIONALLY_ACCEPTED_HOST_DYNAMIC_BASELINE";
        internal static void Require()
        {
            if (!Authorized()) throw new CeremonyException("SOURCE_DISABLED", false);
        }
        private static bool Authorized()
        {
            return SourceFlag() &&
                !Launcher.ACCOUNT_EFFECT_AUTHORIZATION_ID.StartsWith("NOT-AUTHORIZED", StringComparison.Ordinal);
        }
        private static bool SourceFlag() { return Launcher.ACCOUNT_EFFECT_EXECUTION_AUTHORIZED; }
        internal static void Check(bool condition, string code)
        {
            if (!condition) throw new CeremonyException(code, false);
        }
    }

    internal sealed class CeremonyException : Exception
    {
        internal readonly string Code;
        internal readonly bool EffectMayHaveOccurred;
        internal CeremonyException(string code, bool effect) : base(code)
        { Code = code; EffectMayHaveOccurred = effect; }
    }

    // Only JSON primitives can enter this closed, recursively validated model.
    // Native handles, SecureString, arbitrary objects and floating point values
    // have no representation. Never pass a native structure to this serializer.
    internal static class J
    {
        internal static Dictionary<string, object> O(params object[] pairs)
        {
            Gate.Check(pairs.Length % 2 == 0, "FIELDS");
            var result = new Dictionary<string, object>(StringComparer.Ordinal);
            for (int i = 0; i < pairs.Length; i += 2) result.Add((string)pairs[i], pairs[i + 1]);
            return result;
        }
        internal static List<object> A(params object[] values) { return new List<object>(values); }
        internal static Dictionary<string, object> Obj(object value)
        { Gate.Check(value is Dictionary<string, object>, "OBJECT"); return (Dictionary<string, object>)value; }
        internal static List<object> Arr(object value)
        { Gate.Check(value is List<object>, "ARRAY"); return (List<object>)value; }
        internal static string S(object value)
        { Gate.Check(value is string, "STRING"); return (string)value; }
        internal static ulong N(object value)
        { Gate.Check(value is ulong, "INTEGER"); return (ulong)value; }
        internal static bool B(object value)
        { Gate.Check(value is bool, "BOOLEAN"); return (bool)value; }
        internal static void Fields(object value, string names)
        {
            var o = Obj(value);
            Gate.Check(o.Keys.OrderBy(x => x, StringComparer.Ordinal).SequenceEqual(
                names.Split(' ').OrderBy(x => x, StringComparer.Ordinal)), "FIELDS");
        }
        internal static void Eq(object value, object expected)
        { Gate.Check(Object.Equals(value, expected), "VALUE"); }
        internal static void Text(object value)
        { Gate.Check(S(value).Length > 0 && S(value).All(c => !Char.IsControl(c)), "TEXT"); }
        internal static void Hex(object value, int length)
        { Gate.Check(Regex.IsMatch(S(value), "\\A[0-9a-f]{" + length + "}\\z"), "HEX"); }
        internal static void Sid(object value)
        {
            string s = S(value);
            Gate.Check(Regex.IsMatch(s, @"\AS-1-(0|[1-9][0-9]*)(-(0|[1-9][0-9]*)){1,15}\z"), "SID");
            string[] p = s.Split('-');
            ulong a;
            Gate.Check(UInt64.TryParse(p[2], NumberStyles.None, CultureInfo.InvariantCulture, out a) && a <= 281474976710655UL, "SID");
            for (int i = 3; i < p.Length; i++)
                Gate.Check(UInt64.TryParse(p[i], NumberStyles.None, CultureInfo.InvariantCulture, out a) && a <= UInt32.MaxValue, "SID");
        }
        internal static void CandidateSid(object value)
        {
            Sid(value);
            string s = S(value);
            Gate.Check(s.Substring(0, s.LastIndexOf('-')) == Gate.MachineSid &&
                s != Launcher.CREATOR_SID && s != Launcher.TRADING_SID, "CANDIDATE_SID");
        }
        internal static byte[] Bytes(object value)
        { var b = new StringBuilder(); Write(b, value); return new UTF8Encoding(false, true).GetBytes(b.ToString()); }
        internal static string Hash(byte[] bytes)
        { using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }
        internal static object Clone(object value) { return Parse(Bytes(value)); }
        private static void Write(StringBuilder b, object v)
        {
            if (v == null) { b.Append("null"); return; }
            if (v is bool) { b.Append((bool)v ? "true" : "false"); return; }
            if (v is ulong) { b.Append(((ulong)v).ToString(CultureInfo.InvariantCulture)); return; }
            if (v is string)
            {
                b.Append('"'); string s = (string)v;
                for (int i = 0; i < s.Length; i++)
                {
                    char c = s[i];
                    if (c == '"' || c == '\\') b.Append('\\').Append(c);
                    else if (c < 32) b.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                    else if (Char.IsHighSurrogate(c))
                    { Gate.Check(i + 1 < s.Length && Char.IsLowSurrogate(s[i + 1]), "UNICODE"); b.Append(c).Append(s[++i]); }
                    else { Gate.Check(!Char.IsLowSurrogate(c), "UNICODE"); b.Append(c); }
                }
                b.Append('"'); return;
            }
            if (v is Dictionary<string, object>)
            {
                b.Append('{'); bool first = true;
                foreach (var p in Obj(v).OrderBy(x => x.Key, StringComparer.Ordinal))
                { if (!first) b.Append(','); first = false; Write(b, p.Key); b.Append(':'); Write(b, p.Value); }
                b.Append('}'); return;
            }
            if (v is List<object>)
            {
                b.Append('['); bool first = true;
                foreach (object x in Arr(v)) { if (!first) b.Append(','); first = false; Write(b, x); }
                b.Append(']'); return;
            }
            throw new CeremonyException("NON_JSON_VALUE", false);
        }
        internal static object Parse(byte[] bytes)
        {
            Gate.Check(bytes != null && bytes.Length > 0 && bytes.Length <= 4194304, "JSON_SIZE");
            string s = new UTF8Encoding(false, true).GetString(bytes);
            var parser = new Parser(s); object result = parser.Value(0);
            Gate.Check(parser.End && Bytes(result).SequenceEqual(bytes), "NONCANONICAL_JSON");
            return result;
        }
        private sealed class Parser
        {
            private readonly string s; private int p;
            internal Parser(string text) { s = text; }
            internal bool End { get { return p == s.Length; } }
            private char Take() { Gate.Check(p < s.Length, "JSON_EOF"); return s[p++]; }
            private void Expect(char c) { Gate.Check(Take() == c, "JSON_SYNTAX"); }
            internal object Value(int depth)
            {
                Gate.Check(depth < 32 && p < s.Length, "JSON_DEPTH"); char c = s[p];
                if (c == '"') return String();
                if (c == '{')
                {
                    p++; var o = O(); if (p < s.Length && s[p] == '}') { p++; return o; }
                    while (true)
                    {
                        string k = String(); Expect(':'); Gate.Check(!o.ContainsKey(k), "DUPLICATE_KEY");
                        o.Add(k, Value(depth + 1)); c = Take(); if (c == '}') return o; Gate.Check(c == ',', "JSON_SYNTAX");
                    }
                }
                if (c == '[')
                {
                    p++; var a = A(); if (p < s.Length && s[p] == ']') { p++; return a; }
                    while (true) { a.Add(Value(depth + 1)); c = Take(); if (c == ']') return a; Gate.Check(c == ',', "JSON_SYNTAX"); }
                }
                foreach (string word in new[] { "true", "false", "null" })
                    if (p + word.Length <= s.Length && System.String.CompareOrdinal(s, p, word, 0, word.Length) == 0)
                    { p += word.Length; return word == "null" ? null : (object)(word == "true"); }
                int start = p; while (p < s.Length && s[p] >= '0' && s[p] <= '9') p++;
                ulong n; Gate.Check(p > start && UInt64.TryParse(s.Substring(start, p - start), NumberStyles.None, CultureInfo.InvariantCulture, out n), "JSON_INTEGER");
                return UInt64.Parse(s.Substring(start, p - start), CultureInfo.InvariantCulture);
            }
            private string String()
            {
                Expect('"'); var b = new StringBuilder();
                while (true)
                {
                    char c = Take(); if (c == '"') return b.ToString();
                    Gate.Check(c >= 32, "JSON_STRING");
                    if (c == '\\')
                    {
                        c = Take();
                        if (c == '"' || c == '\\') b.Append(c);
                        else
                        {
                            Gate.Check(c == 'u' && p + 4 <= s.Length, "JSON_ESCAPE");
                            ushort n; Gate.Check(UInt16.TryParse(s.Substring(p, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out n), "JSON_ESCAPE");
                            b.Append((char)n); p += 4;
                        }
                    }
                    else b.Append(c);
                }
            }
        }
    }

    internal sealed class EnumPage : IDisposable
    {
        internal uint Status, Entries, TotalHint, Resume;
        internal List<string> Names;
        private Action release;
        internal EnumPage(uint status, uint entries, uint total, uint resume, List<string> names, Action owner)
        { Status = status; Entries = entries; TotalHint = total; Resume = resume; Names = names; release = owner; }
        public void Dispose() { Action r = release; release = null; if (r != null) r(); }
    }
    internal interface IReadAdapter
    {
        uint AbsenceStatus();
        EnumPage UsersPage(uint resume);
        Dictionary<string, object> Token();
        Dictionary<string, object> Account();
        Dictionary<string, object> UsersIdentity();
        Dictionary<string, object> Groups(uint flags);
    }
    internal static class Proof
    {
        internal static Dictionary<string, object> Absence(IReadAdapter api)
        {
            uint status = api.AbsenceStatus(); Gate.Check(status == 2221, status == 0 ? "COLLISION" : "ABSENCE_UNKNOWN");
            uint resume = 0; var seenResume = new HashSet<uint>(); seenResume.Add(0);
            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase); var pages = J.A();
            while (true)
            {
                using (EnumPage page = api.UsersPage(resume))
                {
                    Gate.Check(page != null && page.Names != null && page.Entries == page.Names.Count, "ENUM_BUFFER");
                    Gate.Check(page.Status == 0 || page.Status == 234, "ENUM_STATUS");
                    foreach (string name in page.Names)
                    {
                        Name(name); Gate.Check(names.Add(name), "ENUM_DUPLICATE");
                        Gate.Check(!String.Equals(name, Launcher.CANDIDATE_NAME, StringComparison.OrdinalIgnoreCase), "COLLISION");
                    }
                    bool progress = page.Resume != resume;
                    pages.Add(J.O("status", (ulong)page.Status, "entries_read", (ulong)page.Entries,
                        "total_entries_hint", (ulong)page.TotalHint, "resume_progress", progress));
                    if (page.Status == 0) break;
                    Gate.Check(progress && seenResume.Add(page.Resume), "ENUM_RESUME");
                    resume = page.Resume;
                }
            }
            return J.O("getinfo_level", 1UL, "getinfo_status", 2221UL, "enum_level", 0UL, "enum_filter", 0UL,
                "enum_terminal_status", 0UL, "enum_pages", pages, "exact_name_match_count", 0UL, "result", "DEFINITE_NOT_FOUND");
        }
        internal static void Name(string name)
        { Gate.Check(!String.IsNullOrEmpty(name) && name.Trim() == name && !name.Any(Char.IsControl) && name.IndexOf('\\') < 0 && name.IndexOf('\0') < 0, "NAME"); }
        internal static Dictionary<string, object> Options()
        {
            return J.O("name", Launcher.CANDIDATE_NAME, "level", 1UL, "privilege", 1UL, "flags", 1UL,
                "home_dir", null, "comment", Gate.Comment, "script_path", null, "password_age_initialization", 0UL,
                "defaults_contract", "NETUSERADD_LEVEL1_DOCUMENTED");
        }
        internal static string CreateStatus(uint status)
        { return status == 0 ? "CONFIRMED" : status == 2224 ? "COLLISION" : "UNCERTAIN"; }
        internal static void Account(object value)
        {
            J.Fields(value, "name sid enabled privilege flags machine_domain_sid comment full_name account_expires defaults_readback_passed bidirectional_mapping_passed");
            var a = J.Obj(value); J.Eq(a["name"], Launcher.CANDIDATE_NAME); J.CandidateSid(a["sid"]);
            J.Eq(a["enabled"], true); J.Eq(a["privilege"], 1UL); J.Eq(a["flags"], 0x201UL);
            J.Eq(a["machine_domain_sid"], Gate.MachineSid); J.Eq(a["comment"], Gate.Comment);
            J.Eq(a["full_name"], null); J.Eq(a["account_expires"], (ulong)UInt32.MaxValue);
            J.Eq(a["defaults_readback_passed"], true); J.Eq(a["bidirectional_mapping_passed"], true);
        }
        internal static void Identity(object value)
        {
            J.Fields(value, "sid resolved_name domain sid_type roundtrip_passed"); var o = J.Obj(value);
            J.Eq(o["sid"], Launcher.BUILTIN_USERS_SID); Name(J.S(o["resolved_name"]));
            J.Eq(o["domain"], "BUILTIN"); J.Eq(o["sid_type"], 4UL); J.Eq(o["roundtrip_passed"], true);
        }
        internal static HashSet<string> Groups(object value, ulong flags)
        {
            J.Fields(value, "flags level status entries_read total_entries groups"); var g = J.Obj(value);
            J.Eq(g["flags"], flags); J.Eq(g["level"], 0UL); J.Eq(g["status"], 0UL);
            var list = J.Arr(g["groups"]); J.Eq(g["entries_read"], (ulong)list.Count); J.Eq(g["total_entries"], (ulong)list.Count);
            Sorted(list, "sid name"); var sids = new HashSet<string>(StringComparer.Ordinal);
            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (object v in list)
            { J.Fields(v, "sid name"); var x = J.Obj(v); J.Sid(x["sid"]); Name(J.S(x["name"])); Gate.Check(sids.Add(J.S(x["sid"])) && names.Add(J.S(x["name"])), "GROUP_DUPLICATE"); }
            return sids;
        }
        internal static string Branch(object direct)
        {
            var s = Groups(direct, 0); if (s.Count == 0) return "ADD_USERS";
            Gate.Check(s.SetEquals(new[] { Launcher.BUILTIN_USERS_SID }), "DIRECT_BASELINE"); return "ALREADY_USERS";
        }
        internal static void Sorted(List<object> list, string fields)
        {
            string[] keys = fields.Split(' '); object previous = null;
            foreach (object v in list)
            {
                var x = J.Obj(v);
                foreach (string k in keys) J.Text(x[k]);
                if (previous != null)
                {
                    int cmp = 0;
                    foreach (string k in keys) { cmp = StringComparer.Ordinal.Compare(J.S(J.Obj(previous)[k]), J.S(x[k])); if (cmp != 0) break; }
                    Gate.Check(cmp < 0, "COLLECTION_ORDER_OR_DUPLICATE");
                }
                previous = v;
            }
        }
        internal static void Sort(List<object> list, string fields)
        {
            var keys = fields.Split(' ');
            list.Sort(delegate(object a, object b) {
                foreach (string k in keys) { int c = StringComparer.Ordinal.Compare(J.S(J.Obj(a)[k]), J.S(J.Obj(b)[k])); if (c != 0) return c; }
                return 0;
            }); Sorted(list, fields);
        }
        internal static string PrivilegeDisposition(string name)
        { return BaselinePrivileges.Contains(name) ? "ACCEPTED" : Dangerous.Contains(name) ? "REJECTED" : "UNRESOLVED"; }
        // Microsoft privilege-constants meanings: these ordinary desktop rights
        // do not confer KSP/private-key, ownership, ACL, token, backup or restore
        // authority. System-time, remote-shutdown and management rights are not
        // accepted by analogy. Unknown rights remain unresolved.
        private static readonly HashSet<string> BaselinePrivileges = new HashSet<string>(new[] {
            "SeChangeNotifyPrivilege", "SeShutdownPrivilege", "SeUndockPrivilege", "SeIncreaseWorkingSetPrivilege", "SeTimeZonePrivilege"
        }, StringComparer.Ordinal);
        private static readonly HashSet<string> Dangerous = new HashSet<string>(new[] {
            "SeDebugPrivilege", "SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege", "SeSecurityPrivilege",
            "SeTcbPrivilege", "SeCreateTokenPrivilege", "SeAssignPrimaryTokenPrivilege", "SeImpersonatePrivilege", "SeLoadDriverPrivilege", "SeRelabelPrivilege"
        }, StringComparer.Ordinal);
        internal static string Classification(string sid)
        {
            if (sid == Launcher.BUILTIN_USERS_SID) return "BASELINE";
            if (sid == Launcher.PERFORMANCE_LOG_USERS_SID) return "HOST_DYNAMIC_BASELINE";
            if (new[] { "S-1-1-0", "S-1-2-0", "S-1-2-1", "S-1-5-4", "S-1-5-11", "S-1-5-15", "S-1-5-113", "S-1-5-64-10", "S-1-18-1", "S-1-18-2" }.Contains(sid) ||
                Regex.IsMatch(sid, @"\AS-1-5-5-(0|[1-9][0-9]*)-(0|[1-9][0-9]*)\z")) return "NORMAL_LOGON";
            if (sid == "S-1-16-8192") return "INTEGRITY";
            return "UNKNOWN";
        }
        internal static void TokenShape(object value)
        {
            J.Fields(value, "user_sid token_type elevated elevation_type administrators_present administrators_enabled administrators_deny_only thread_token_absent groups privileges");
            var t = J.Obj(value); J.Sid(t["user_sid"]); Gate.Check(J.N(t["token_type"]) == 1 || J.N(t["token_type"]) == 2, "TOKEN_TYPE");
            J.B(t["elevated"]); Gate.Check(J.N(t["elevation_type"]) >= 1 && J.N(t["elevation_type"]) <= 3, "ELEVATION_TYPE");
            J.B(t["thread_token_absent"]); var groups = J.Arr(t["groups"]); var privileges = J.Arr(t["privileges"]);
            Sorted(groups, "sid name"); Sorted(privileges, "name");
            var sids = new HashSet<string>(); Dictionary<string, object> admin = null;
            foreach (object v in groups)
            {
                J.Fields(v, "sid name attributes classification"); var g = J.Obj(v); J.Sid(g["sid"]); J.Text(g["name"]);
                ulong attributes = J.N(g["attributes"]);
                Gate.Check(sids.Add(J.S(g["sid"])) && attributes <= UInt32.MaxValue && (attributes & ~0xE000007FUL) == 0 && (attributes & 20) != 20, "TOKEN_GROUP");
                Gate.Check(new[] { "BASELINE", "HOST_DYNAMIC_BASELINE", "NORMAL_LOGON", "INTEGRITY", "SPECIAL", "UNKNOWN" }.Contains(J.S(g["classification"])), "CLASSIFICATION");
                J.Eq(g["classification"], Classification(J.S(g["sid"])));
                if (J.S(g["sid"]) == Gate.Administrators) admin = g;
            }
            J.Eq(t["administrators_present"], admin != null);
            J.Eq(t["administrators_enabled"], admin != null && (J.N(admin["attributes"]) & 4) != 0);
            J.Eq(t["administrators_deny_only"], admin != null && (J.N(admin["attributes"]) & 16) != 0);
            foreach (object v in privileges)
            {
                J.Fields(v, "name attributes enabled enabled_by_default removed disposition"); var p = J.Obj(v); J.Text(p["name"]);
                ulong a = J.N(p["attributes"]); Gate.Check(a <= UInt32.MaxValue && (a & ~0x80000007UL) == 0, "PRIVILEGE_ATTRIBUTES");
                J.Eq(p["enabled"], (a & 2) != 0); J.Eq(p["enabled_by_default"], (a & 1) != 0); J.Eq(p["removed"], (a & 4) != 0);
                J.Eq(p["disposition"], PrivilegeDisposition(J.S(p["name"])));
            }
        }
        internal static void Creator(object value)
        {
            TokenShape(value); var t = J.Obj(value); J.Eq(t["user_sid"], Launcher.CREATOR_SID);
            J.Eq(t["token_type"], 1UL); J.Eq(t["elevated"], true); J.Eq(t["elevation_type"], 2UL);
            J.Eq(t["thread_token_absent"], true); J.Eq(t["administrators_present"], true);
            J.Eq(t["administrators_enabled"], true); J.Eq(t["administrators_deny_only"], false);
        }
        internal static void Ordinary(object value, string sid)
        {
            J.CandidateSid(sid); TokenShape(value); var t = J.Obj(value); J.Eq(t["user_sid"], sid);
            J.Eq(t["token_type"], 1UL); J.Eq(t["elevated"], false); J.Eq(t["thread_token_absent"], true);
            Gate.Check(J.N(t["elevation_type"]) == 1 || J.N(t["elevation_type"]) == 3, "ORDINARY_ELEVATION");
            J.Eq(t["administrators_present"], false); J.Eq(t["administrators_enabled"], false); J.Eq(t["administrators_deny_only"], false);
            var groups = J.Arr(t["groups"]);
            Gate.Check(groups.Any(v => J.S(J.Obj(v)["sid"]) == Gate.Interactive && (J.N(J.Obj(v)["attributes"]) & 20) == 4), "INTERACTIVE");
            foreach (object v in groups)
            { var g = J.Obj(v); Gate.Check(Classification(J.S(g["sid"])) != "UNKNOWN", "SPECIAL_GROUP"); }
            var privileges = J.Arr(t["privileges"]); Gate.Check(privileges.Count > 0, "EMPTY_PRIVILEGES");
            foreach (object v in privileges) J.Eq(J.Obj(v)["disposition"], "ACCEPTED");
        }
    }

    internal static class Qualification
    {
        internal static string RightDisposition(string name)
        {
            if (name == "SeInteractiveLogonRight" || name == "SeNetworkLogonRight" ||
                new[] { "SeDenyNetworkLogonRight", "SeDenyRemoteInteractiveLogonRight", "SeDenyBatchLogonRight", "SeDenyServiceLogonRight" }.Contains(name)) return "ACCEPTED";
            return Proof.PrivilegeDisposition(name);
        }
        internal static void Shape(object value)
        {
            J.Fields(value, "account direct_view indirect_view relevant_edges effective_groups rights candidate_token collection_method performance_log_users");
            var o = J.Obj(value); Proof.Account(o["account"]); Proof.Groups(o["direct_view"], 0); Proof.Groups(o["indirect_view"], 1);
            Proof.TokenShape(o["candidate_token"]); J.Eq(o["collection_method"], "operator_observed_console");
            var edges = J.Arr(o["relevant_edges"]); Proof.Sorted(edges, "member_sid group_sid origin");
            var pairs = new HashSet<string>();
            foreach (object v in edges)
            {
                J.Fields(v, "member_sid group_sid origin"); var e = J.Obj(v); J.Sid(e["member_sid"]); J.Sid(e["group_sid"]); Origin(e["origin"]);
                Gate.Check(pairs.Add(J.S(e["member_sid"]) + "/" + J.S(e["group_sid"])), "EDGE_DUPLICATE");
            }
            var effective = J.Arr(o["effective_groups"]); Proof.Sorted(effective, "sid name"); var sids = new HashSet<string>();
            foreach (object v in effective)
            {
                J.Fields(v, "sid name attributes origin disposition"); var g = J.Obj(v); J.Sid(g["sid"]); J.Text(g["name"]);
                Gate.Check(sids.Add(J.S(g["sid"])) && J.N(g["attributes"]) <= UInt32.MaxValue, "EFFECTIVE_GROUP"); Origin(g["origin"]); Disposition(g["disposition"]);
            }
            var rights = J.Arr(o["rights"]); Proof.Sorted(rights, "principal_sid name origin");
            foreach (object v in rights)
            {
                J.Fields(v, "principal_sid name origin disposition"); var r = J.Obj(v); J.Sid(r["principal_sid"]); J.Text(r["name"]);
                Origin(r["origin"]); J.Eq(r["disposition"], RightDisposition(J.S(r["name"])));
            }
            var p = J.Obj(o["performance_log_users"]);
            J.Fields(p, "classification effective direct_assignment interactive_enabled host_edge_present alternate_path_present provenance_passed");
            J.Eq(p["classification"], Gate.PerformanceClass);
            foreach (string k in new[] { "effective", "direct_assignment", "interactive_enabled", "host_edge_present", "alternate_path_present", "provenance_passed" }) J.B(p[k]);
        }
        private static void Origin(object v) { Gate.Check(new[] { "DIRECT", "NESTED", "LOGON_CONTEXT" }.Contains(J.S(v)), "ORIGIN"); }
        private static void Disposition(object v) { Gate.Check(new[] { "ACCEPTED", "REJECTED", "UNRESOLVED" }.Contains(J.S(v)), "DISPOSITION"); }
        internal static HashSet<string> Reach(IEnumerable<string> seeds, List<object> edges, bool excludeReviewedEdge)
        {
            var reached = new HashSet<string>(StringComparer.Ordinal);
            var active = new HashSet<string>(StringComparer.Ordinal);
            Action<string> visit = null;
            visit = delegate(string sid) {
                Gate.Check(!active.Contains(sid), "GROUP_CYCLE");
                if (reached.Contains(sid)) return;
                active.Add(sid);
                foreach (object v in edges)
                {
                    var e = J.Obj(v); if (J.S(e["member_sid"]) != sid) continue;
                    if (excludeReviewedEdge && sid == Gate.Interactive && J.S(e["group_sid"]) == Launcher.PERFORMANCE_LOG_USERS_SID) continue;
                    visit(J.S(e["group_sid"]));
                }
                active.Remove(sid); reached.Add(sid);
            };
            foreach (string s in seeds) visit(s);
            return reached;
        }
        internal static void Accept(object value)
        {
            Shape(value); var o = J.Obj(value); string sid = J.S(J.Obj(o["account"])["sid"]);
            Proof.Ordinary(o["candidate_token"], sid);
            var direct = Proof.Groups(o["direct_view"], 0); var indirect = Proof.Groups(o["indirect_view"], 1);
            Gate.Check(direct.SetEquals(new[] { Launcher.BUILTIN_USERS_SID }) && indirect.SetEquals(direct), "DIRECT_INDIRECT");
            var edges = J.Arr(o["relevant_edges"]);
            var directEdges = new HashSet<string>(edges.Where(e => J.S(J.Obj(e)["member_sid"]) == sid).Select(e => J.S(J.Obj(e)["group_sid"])));
            Gate.Check(directEdges.SetEquals(direct), "DIRECT_EDGE_MISMATCH");
            var tokenGroups = J.Arr(J.Obj(o["candidate_token"])["groups"]);
            var tokenSids = new HashSet<string>(tokenGroups.Select(g => J.S(J.Obj(g)["sid"])));
            Gate.Check(direct.IsSubsetOf(tokenSids), "MISSING_TOKEN_BASELINE");
            var accountReach = Reach(new[] { sid }, edges, false); accountReach.Remove(sid);
            Gate.Check(accountReach.SetEquals(direct), "ACCOUNT_NESTED_AUTHORITY");
            var logonSeeds = tokenGroups.Where(g => (J.N(J.Obj(g)["attributes"]) & 20) == 4 &&
                J.S(J.Obj(g)["sid"]) != Launcher.PERFORMANCE_LOG_USERS_SID).Select(g => J.S(J.Obj(g)["sid"]));
            var alternate = Reach(logonSeeds.Concat(new[] { sid }), edges, true);
            bool hostEdge = edges.Any(e => J.S(J.Obj(e)["member_sid"]) == Gate.Interactive && J.S(J.Obj(e)["group_sid"]) == Launcher.PERFORMANCE_LOG_USERS_SID);
            bool hasPerformance = tokenSids.Contains(Launcher.PERFORMANCE_LOG_USERS_SID);
            var p = J.Obj(o["performance_log_users"]);
            J.Eq(p["effective"], hasPerformance); J.Eq(p["direct_assignment"], false); J.Eq(p["interactive_enabled"], true);
            J.Eq(p["host_edge_present"], hostEdge); J.Eq(p["alternate_path_present"], alternate.Contains(Launcher.PERFORMANCE_LOG_USERS_SID));
            Gate.Check(!alternate.Contains(Launcher.PERFORMANCE_LOG_USERS_SID), "PERFORMANCE_ALTERNATE");
            // If absent, the token need not contain this special group. If present,
            // simultaneous SID presence is insufficient: prove the sole host edge.
            Gate.Check(!hasPerformance || hostEdge, "PERFORMANCE_PROVENANCE"); J.Eq(p["provenance_passed"], true);
            var fullReach = Reach(logonSeeds.Concat(new[] { sid }), edges, false); fullReach.Remove(sid);
            foreach (string s in fullReach) Gate.Check(Proof.Classification(s) != "UNKNOWN", "UNREVIEWED_GRAPH_GROUP");
            var effective = J.Arr(o["effective_groups"]);
            Gate.Check(effective.Count == tokenGroups.Count, "EFFECTIVE_COUNT");
            foreach (object v in effective)
            {
                var g = J.Obj(v); string s = J.S(g["sid"]);
                var original = tokenGroups.SingleOrDefault(x => J.S(J.Obj(x)["sid"]) == s);
                Gate.Check(original != null, "EFFECTIVE_SID");
                J.Eq(g["attributes"], J.Obj(original)["attributes"]); J.Eq(g["name"], J.Obj(original)["name"]);
                J.Eq(g["origin"], direct.Contains(s) ? "DIRECT" : "LOGON_CONTEXT"); J.Eq(g["disposition"], "ACCEPTED");
            }
            foreach (object v in J.Arr(o["rights"]))
            {
                var r = J.Obj(v); string principal = J.S(r["principal_sid"]);
                Gate.Check(principal == sid || tokenSids.Contains(principal), "RIGHT_PRINCIPAL");
                J.Eq(r["origin"], principal == sid ? "DIRECT" : "NESTED"); J.Eq(r["disposition"], "ACCEPTED");
            }
        }
    }

    internal static class Evidence
    {
        internal static readonly string[] Lifecycle = { "ACCOUNT_CREATION_ATTEMPTED", "ACCOUNT_CREATED", "ACCOUNT_SID_READ_BACK",
            "USERS_ASSIGNMENT_ATTEMPTED", "USERS_ASSIGNMENT_CONFIRMED", "GROUPS_QUALIFIED", "TOKEN_QUALIFIED" };
        private static readonly Dictionary<string, string> FactFields = new Dictionary<string, string>(StringComparer.Ordinal) {
            { "PREFLIGHT", "creator_token absence root_absent root_identity tools users_identity baseline_mode" },
            { "ACCOUNT_CREATION_ATTEMPTED", "absence creator_token secure_input_method creation_surface options" },
            { "ACCOUNT_CREATED", "net_status creation_return_confirmed password_buffer_zero_freed securestring_disposed" },
            { "ACCOUNT_SID_READ_BACK", "account" },
            { "USERS_BASELINE_SELECTED", "branch direct_view users_identity" },
            { "USERS_ASSIGNMENT_ATTEMPTED", "group_sid member_sid creator_token direct_view users_identity" },
            { "USERS_ASSIGNMENT_CONFIRMED", "group_sid member_sid net_status direct_view identity_continuity_passed" },
            { "QUALIFICATION_OBSERVED", "account direct_view indirect_view relevant_edges effective_groups rights candidate_token collection_method performance_log_users" },
            { "GROUPS_QUALIFIED", "observation_sha256 direct_baseline_passed indirect_review_passed special_authority_review_passed privileges_review_passed" },
            { "TOKEN_QUALIFIED", "observation_sha256 token_gate_passed enabled_recheck_passed identity_continuity_passed" },
            { "STOP", "last_confirmed_sequence reason api_name net_status parameter_error_index" }
        };
        internal static string Next(List<byte[]> chain)
        {
            if (chain.Count == 0) return "PREFLIGHT";
            var r = J.Obj(J.Parse(chain[chain.Count - 1])); string e = J.S(r["event"]);
            switch (e)
            {
                case "PREFLIGHT": return "ACCOUNT_CREATION_ATTEMPTED";
                case "ACCOUNT_CREATION_ATTEMPTED": return "ACCOUNT_CREATED";
                case "ACCOUNT_CREATED": return "ACCOUNT_SID_READ_BACK";
                case "ACCOUNT_SID_READ_BACK": return "USERS_BASELINE_SELECTED";
                case "USERS_BASELINE_SELECTED": return J.S(J.Obj(r["facts"])["branch"]) == "ADD_USERS" ? "USERS_ASSIGNMENT_ATTEMPTED" : "QUALIFICATION_OBSERVED";
                case "USERS_ASSIGNMENT_ATTEMPTED": return "USERS_ASSIGNMENT_CONFIRMED";
                case "USERS_ASSIGNMENT_CONFIRMED": return "QUALIFICATION_OBSERVED";
                case "QUALIFICATION_OBSERVED": return "GROUPS_QUALIFIED";
                case "GROUPS_QUALIFIED": return "TOKEN_QUALIFIED";
                default: return null;
            }
        }
        internal static Dictionary<string, object> CeremonyIdentity(string commit, string tree)
        {
            return J.O("source_commit", commit, "source_tree", tree, "evidence_root", Launcher.CEREMONY_EVIDENCE_ROOT,
                "candidate_name", Launcher.CANDIDATE_NAME, "creator_sid", Launcher.CREATOR_SID, "trading_sid", Launcher.TRADING_SID);
        }
        internal static byte[] Make(List<byte[]> prior, string ev, Dictionary<string, object> facts, Dictionary<string, object> host, string utc,
            string outcome, Dictionary<string, object> failure)
        {
            Validate(prior);
            var life = J.O(); foreach (string flag in Lifecycle) life.Add(flag, false);
            if (prior.Count > 0) life = J.Obj(J.Clone(J.Obj(J.Parse(prior[prior.Count - 1]))["lifecycle"]));
            if (Lifecycle.Contains(ev)) life[ev] = true;
            Gate.Check(prior.Count > 0 || ev == "PREFLIGHT", "PREFLIGHT_REQUIRED");
            object ceremony = prior.Count > 0 ? J.Obj(J.Parse(prior[0]))["ceremony"] :
                CeremonyIdentity(J.S(J.Obj(facts["tools"])["helper_source_commit"]), J.S(J.Obj(facts["tools"])["helper_source_tree"]));
            var record = J.O("schema", Gate.Schema, "sequence", (ulong)prior.Count + 1, "previous_sha256", prior.Count == 0 ? null : J.Hash(prior[prior.Count - 1]),
                "event", ev, "outcome", outcome, "utc", utc, "host", host, "ceremony", ceremony, "lifecycle", life, "facts", facts, "failure", failure);
            byte[] bytes = J.Bytes(record); var trial = new List<byte[]>(prior); trial.Add(bytes); Validate(trial); return bytes;
        }
        internal static void Validate(List<byte[]> chain)
        {
            Gate.Check(chain != null && chain.Count <= 999, "CHAIN_SIZE"); var prefix = new List<byte[]>();
            Dictionary<string, object> previous = null; Dictionary<string, object> observed = null;
            string candidateSid = null, observationHash = null, usersName = null;
            foreach (byte[] bytes in chain)
            {
                var r = J.Obj(J.Parse(bytes));
                J.Fields(r, "schema sequence previous_sha256 event outcome utc host ceremony lifecycle facts failure");
                J.Eq(r["schema"], Gate.Schema); J.Eq(r["sequence"], (ulong)prefix.Count + 1);
                J.Eq(r["previous_sha256"], prefix.Count == 0 ? null : J.Hash(prefix[prefix.Count - 1]));
                string ev = J.S(r["event"]); Gate.Check(FactFields.ContainsKey(ev), "EVENT");
                Gate.Check(ev == "STOP" ? previous == null || J.S(previous["event"]) != "STOP" : ev == Next(prefix), "EVENT_ORDER");
                DateTime timestamp;
                Gate.Check(DateTime.TryParseExact(J.S(r["utc"]), "yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out timestamp), "UTC");
                J.Fields(r["host"], "name machine_domain_sid os_version"); var host = J.Obj(r["host"]);
                J.Eq(host["name"], Launcher.HOST); J.Eq(host["machine_domain_sid"], Gate.MachineSid); J.Text(host["os_version"]);
                var ceremony = J.Obj(r["ceremony"]); J.Hex(ceremony["source_commit"], 40); J.Hex(ceremony["source_tree"], 40);
                Gate.Check(J.S(ceremony["source_commit"]).Trim('0').Length > 0 && J.S(ceremony["source_tree"]).Trim('0').Length > 0, "SOURCE_IDENTITY");
                Gate.Check(J.Bytes(ceremony).SequenceEqual(J.Bytes(CeremonyIdentity(J.S(ceremony["source_commit"]), J.S(ceremony["source_tree"])))), "CEREMONY_IDENTITY");
                if (previous != null) Gate.Check(J.Bytes(ceremony).SequenceEqual(J.Bytes(previous["ceremony"])), "SOURCE_DRIFT");
                if (previous != null) Gate.Check(J.Bytes(previous["host"]).SequenceEqual(J.Bytes(host)), "HOST_DRIFT");
                J.Fields(r["lifecycle"], String.Join(" ", Lifecycle)); var life = J.Obj(r["lifecycle"]);
                foreach (string flag in Lifecycle)
                {
                    bool before = previous != null && J.B(J.Obj(previous["lifecycle"])[flag]);
                    J.Eq(life[flag], before || ev == flag);
                }
                var f = J.Obj(r["facts"]); J.Fields(f, FactFields[ev]);
                if (ev == "STOP")
                {
                    Gate.Check(new[] { "FAILED", "UNCERTAIN", "BLOCKED" }.Contains(J.S(r["outcome"])), "STOP_OUTCOME");
                    J.Fields(r["failure"], "boundary code effect_may_have_occurred"); var fail = J.Obj(r["failure"]);
                    Gate.Check(new[] { "PREFLIGHT", "SECURE_INPUT", "CREATE", "READBACK", "USERS", "QUALIFICATION", "RETENTION" }.Contains(J.S(fail["boundary"])), "FAILURE_BOUNDARY");
                    Gate.Check(new[] { "GATE_REJECTED", "COLLISION", "NATIVE_FAILURE", "UNCERTAIN", "RETENTION_UNCERTAIN" }.Contains(J.S(fail["code"])), "FAILURE_CODE");
                    J.B(fail["effect_may_have_occurred"]); J.Eq(f["last_confirmed_sequence"], (ulong)prefix.Count); J.Eq(f["reason"], fail["code"]);
                    Gate.Check(new[] { "NONE", "NetUserAdd", "NetLocalGroupAddMembers", "NetUserGetInfo", "NetUserEnum", "NetUserGetLocalGroups" }.Contains(J.S(f["api_name"])), "API_NAME");
                    if (f["net_status"] != null) Gate.Check(J.N(f["net_status"]) <= UInt32.MaxValue, "STATUS");
                    if (f["parameter_error_index"] != null)
                        Gate.Check(J.S(f["api_name"]) == "NetUserAdd" && Object.Equals(f["net_status"], 87UL) && J.N(f["parameter_error_index"]) >= 1 && J.N(f["parameter_error_index"]) <= 8, "PARAMETER_INDEX");
                    if (J.B(fail["effect_may_have_occurred"])) J.Eq(r["outcome"], "UNCERTAIN");
                }
                else
                {
                    J.Eq(r["outcome"], "PASS"); J.Eq(r["failure"], null);
                    switch (ev)
                    {
                        case "PREFLIGHT":
                            Proof.Creator(f["creator_token"]); Absence(f["absence"]); J.Eq(f["root_absent"], true);
                            J.Fields(f["root_identity"], "volume_serial file_id owner_sid dacl_sddl"); var root = J.Obj(f["root_identity"]);
                            Gate.Check(J.N(root["volume_serial"]) <= UInt32.MaxValue, "VOLUME"); J.Hex(root["file_id"], 16); J.Sid(root["owner_sid"]); J.Text(root["dacl_sddl"]);
                            J.Fields(f["tools"], "powershell_version helper_source_commit helper_source_tree helper_sha256 netapi32_version"); var tools = J.Obj(f["tools"]);
                            J.Text(tools["powershell_version"]); Gate.Check(J.S(tools["powershell_version"]).StartsWith("5.1.", StringComparison.Ordinal), "POWERSHELL_VERSION");
                            J.Eq(tools["helper_source_commit"], ceremony["source_commit"]); J.Eq(tools["helper_source_tree"], ceremony["source_tree"]);
                            J.Hex(tools["helper_sha256"], 64); Gate.Check(J.S(tools["helper_sha256"]).Trim('0').Length > 0, "HELPER_HASH"); J.Text(tools["netapi32_version"]);
                            Proof.Identity(f["users_identity"]); usersName = J.S(J.Obj(f["users_identity"])["resolved_name"]); J.Eq(f["baseline_mode"], "CONDITIONAL_USERS"); break;
                        case "ACCOUNT_CREATION_ATTEMPTED":
                            Proof.Creator(f["creator_token"]); Absence(f["absence"]);
                            J.Eq(f["secure_input_method"], "READ_HOST_SECURESTRING_GLOBALALLOCUNICODE"); J.Eq(f["creation_surface"], "NETAPI32_NETUSERADD_LEVEL1");
                            Gate.Check(J.Bytes(f["options"]).SequenceEqual(J.Bytes(Proof.Options())), "OPTIONS"); break;
                        case "ACCOUNT_CREATED":
                            J.Eq(f["net_status"], 0UL); foreach (string k in new[] { "creation_return_confirmed", "password_buffer_zero_freed", "securestring_disposed" }) J.Eq(f[k], true); break;
                        case "ACCOUNT_SID_READ_BACK":
                            Proof.Account(f["account"]); candidateSid = J.S(J.Obj(f["account"])["sid"]); break;
                        case "USERS_BASELINE_SELECTED":
                            J.Eq(f["branch"], Proof.Branch(f["direct_view"])); Proof.Identity(f["users_identity"]);
                            J.Eq(J.Obj(f["users_identity"])["resolved_name"], usersName); break;
                        case "USERS_ASSIGNMENT_ATTEMPTED":
                            J.Eq(f["group_sid"], Launcher.BUILTIN_USERS_SID); J.Eq(f["member_sid"], candidateSid);
                            Proof.Creator(f["creator_token"]); Gate.Check(Proof.Groups(f["direct_view"], 0).Count == 0, "USERS_NOT_EMPTY");
                            Proof.Identity(f["users_identity"]); J.Eq(J.Obj(f["users_identity"])["resolved_name"], usersName); break;
                        case "USERS_ASSIGNMENT_CONFIRMED":
                            J.Eq(f["group_sid"], Launcher.BUILTIN_USERS_SID); J.Eq(f["member_sid"], candidateSid); J.Eq(f["net_status"], 0UL);
                            J.Eq(Proof.Branch(f["direct_view"]), "ALREADY_USERS"); J.Eq(f["identity_continuity_passed"], true); break;
                        case "QUALIFICATION_OBSERVED":
                            Qualification.Shape(f); J.Eq(J.Obj(f["account"])["sid"], candidateSid); observed = f; observationHash = J.Hash(bytes); break;
                        case "GROUPS_QUALIFIED":
                            Gate.Check(observed != null, "OBSERVATION_MISSING"); Qualification.Accept(observed); J.Eq(f["observation_sha256"], observationHash);
                            foreach (string k in new[] { "direct_baseline_passed", "indirect_review_passed", "special_authority_review_passed", "privileges_review_passed" }) J.Eq(f[k], true); break;
                        case "TOKEN_QUALIFIED":
                            Gate.Check(observed != null, "OBSERVATION_MISSING"); Qualification.Accept(observed); J.Eq(f["observation_sha256"], observationHash);
                            foreach (string k in new[] { "token_gate_passed", "enabled_recheck_passed", "identity_continuity_passed" }) J.Eq(f[k], true); break;
                    }
                }
                previous = r; prefix.Add(bytes);
            }
        }
        private static void Absence(object value)
        {
            J.Fields(value, "getinfo_level getinfo_status enum_level enum_filter enum_terminal_status enum_pages exact_name_match_count result"); var a = J.Obj(value);
            J.Eq(a["getinfo_level"], 1UL); J.Eq(a["getinfo_status"], 2221UL); J.Eq(a["enum_level"], 0UL); J.Eq(a["enum_filter"], 0UL);
            J.Eq(a["enum_terminal_status"], 0UL); J.Eq(a["exact_name_match_count"], 0UL); J.Eq(a["result"], "DEFINITE_NOT_FOUND");
            var pages = J.Arr(a["enum_pages"]); Gate.Check(pages.Count > 0, "ENUM_EMPTY_PROOF");
            for (int i = 0; i < pages.Count; i++)
            {
                var p = J.Obj(pages[i]); J.Fields(p, "status entries_read total_entries_hint resume_progress");
                J.Eq(p["status"], i == pages.Count - 1 ? 0UL : 234UL); J.B(p["resume_progress"]);
                if (i < pages.Count - 1) J.Eq(p["resume_progress"], true);
                Gate.Check(J.N(p["entries_read"]) <= UInt32.MaxValue && J.N(p["total_entries_hint"]) <= UInt32.MaxValue, "ENUM_COUNTS");
            }
        }
    }

    internal interface IStore
    {
        List<byte[]> Load();
        void Publish(byte[] record);
    }
    internal interface IRecordFiles
    {
        string[] Names();
        byte[] Read(string name);
        void CreateNew(string name, byte[] bytes);
    }
    // Shared loader/publication authority; tests replace only file I/O. The
    // production implementation below supplies only the source-fixed root.
    internal sealed class RecordArchive : IStore
    {
        private readonly IRecordFiles files;
        internal RecordArchive(IRecordFiles storage) { files = storage; }
        private static string Name(int sequence)
        { return "record-" + sequence.ToString("D3", CultureInfo.InvariantCulture) + ".json"; }
        public List<byte[]> Load()
        {
            string[] names = files.Names(); Array.Sort(names, StringComparer.Ordinal);
            Gate.Check(names.Length <= 999, "ROOT_ENTRIES"); var chain = new List<byte[]>();
            for (int i = 0; i < names.Length; i++)
            { Gate.Check(names[i] == Name(i + 1), "ROOT_ENTRY_OR_GAP"); chain.Add(files.Read(names[i])); }
            Evidence.Validate(chain); return chain;
        }
        public void Publish(byte[] bytes)
        {
            var chain = Load(); var intended = new List<byte[]>(chain); intended.Add(bytes); Evidence.Validate(intended);
            files.CreateNew(Name(intended.Count), bytes);
            var loaded = Load(); Gate.Check(loaded.Count == intended.Count, "PUBLISH_RELOAD_COUNT");
            for (int i = 0; i < intended.Count; i++) Gate.Check(loaded[i].SequenceEqual(intended[i]), "PUBLISH_RELOAD_BYTES");
        }
    }
    internal sealed class Journal
    {
        private readonly IStore store;
        private readonly Dictionary<string, object> host;
        private readonly HashSet<string> dispatched = new HashSet<string>(StringComparer.Ordinal);
        internal List<byte[]> Confirmed { get; private set; }
        internal bool Halted { get; private set; }
        internal bool EffectMayHaveOccurred { get; private set; }
        internal Journal(IStore target, Dictionary<string, object> observedHost)
        {
            store = target; host = J.Obj(J.Clone(observedHost)); Confirmed = target.Load(); Evidence.Validate(Confirmed);
            foreach (byte[] bytes in Confirmed)
            {
                string ev = J.S(J.Obj(J.Parse(bytes))["event"]);
                if (ev == "ACCOUNT_CREATION_ATTEMPTED" || ev == "USERS_ASSIGNMENT_ATTEMPTED") { dispatched.Add(ev); EffectMayHaveOccurred = true; }
            }
        }
        internal void Advance(string ev, Dictionary<string, object> facts)
        {
            Gate.Check(!Halted, "RUNNER_HALTED");
            byte[] bytes = Evidence.Make(Confirmed, ev, facts, host, DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", CultureInfo.InvariantCulture), "PASS", null);
            try
            {
                store.Publish(bytes); var reloaded = store.Load(); Evidence.Validate(reloaded);
                Gate.Check(reloaded.Count == Confirmed.Count + 1, "RELOAD_COUNT");
                for (int i = 0; i < Confirmed.Count; i++) Gate.Check(reloaded[i].SequenceEqual(Confirmed[i]), "RELOAD_PREFIX");
                Gate.Check(reloaded[reloaded.Count - 1].SequenceEqual(bytes), "RELOAD_BYTES");
                Confirmed = reloaded;
            }
            catch { Halted = true; throw new CeremonyException("RETENTION_UNCERTAIN", EffectMayHaveOccurred); }
        }
        internal void BeginDispatch(string attemptedEvent)
        {
            Gate.Check(!Halted && Confirmed.Count > 0 && J.S(J.Obj(J.Parse(Confirmed[Confirmed.Count - 1]))["event"]) == attemptedEvent, "DISPATCH_STATE");
            Gate.Check((attemptedEvent == "ACCOUNT_CREATION_ATTEMPTED" || attemptedEvent == "USERS_ASSIGNMENT_ATTEMPTED") && dispatched.Add(attemptedEvent), "DISPATCH_CONSUMED");
            EffectMayHaveOccurred = true;
        }
        internal void Halt() { Halted = true; }
        internal void Stop(string boundary, string code, string api, uint? status, uint? parameter)
        {
            if (Halted) throw new CeremonyException("RUNNER_HALTED", EffectMayHaveOccurred);
            Halted = true; // One attempt at retaining STOP; never recursively persist.
            var f = J.O("last_confirmed_sequence", (ulong)Confirmed.Count, "reason", code, "api_name", api,
                "net_status", status.HasValue ? (object)(ulong)status.Value : null, "parameter_error_index", parameter.HasValue ? (object)(ulong)parameter.Value : null);
            var failure = J.O("boundary", boundary, "code", code, "effect_may_have_occurred", EffectMayHaveOccurred);
            byte[] bytes = Evidence.Make(Confirmed, "STOP", f, host, DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", CultureInfo.InvariantCulture),
                EffectMayHaveOccurred ? "UNCERTAIN" : "BLOCKED", failure);
            try
            {
                store.Publish(bytes); var loaded = store.Load(); Evidence.Validate(loaded);
                Gate.Check(loaded.Count == Confirmed.Count + 1 && loaded.Last().SequenceEqual(bytes), "STOP_RELOAD");
                for (int i = 0; i < Confirmed.Count; i++) Gate.Check(loaded[i].SequenceEqual(Confirmed[i]), "STOP_PREFIX");
                Confirmed = loaded;
            }
            catch { throw new CeremonyException("RETENTION_UNCERTAIN", EffectMayHaveOccurred); }
        }
    }

    // Fake effects have a separate nominal interface. WindowsAdapter never
    // implements it, and this test runner cannot construct a real adapter.
    internal interface ITestEffects
    {
        uint Create();
        uint AddUsers();
    }
    internal sealed class TestEffectRunner
    {
        private readonly Journal journal; private readonly ITestEffects fake;
        private bool used;
        internal TestEffectRunner(Journal state, ITestEffects effects) { journal = state; fake = effects; }
        internal void Execute(string attempt, Dictionary<string, object> before, string confirmed, Dictionary<string, object> after)
        {
            Gate.Check(!used, "TEST_RUNNER_CONSUMED"); used = true;
            Gate.Check(attempt == "ACCOUNT_CREATION_ATTEMPTED" || attempt == "USERS_ASSIGNMENT_ATTEMPTED", "TEST_EFFECT");
            journal.Advance(attempt, before); journal.BeginDispatch(attempt);
            try
            {
                uint status = attempt == "ACCOUNT_CREATION_ATTEMPTED" ? fake.Create() : fake.AddUsers();
                if (status != 0) { journal.Halt(); throw new CeremonyException("UNCERTAIN", true); }
                journal.Advance(confirmed, after);
            }
            catch { journal.Halt(); throw; }
        }
    }

    internal static class Native
    {
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        internal struct USER_INFO_1
        {
            [MarshalAs(UnmanagedType.LPWStr)] internal string name;
            internal IntPtr password;
            internal uint password_age, privilege;
            [MarshalAs(UnmanagedType.LPWStr)] internal string home_dir;
            [MarshalAs(UnmanagedType.LPWStr)] internal string comment;
            internal uint flags;
            [MarshalAs(UnmanagedType.LPWStr)] internal string script_path;
        }
        [StructLayout(LayoutKind.Sequential)]
        internal struct USER_INFO_2
        {
            internal IntPtr name, password;
            internal uint password_age, privilege;
            internal IntPtr home_dir, comment;
            internal uint flags;
            internal IntPtr script_path;
            internal uint auth_flags;
            internal IntPtr full_name, user_comment, parameters, workstations;
            internal uint last_logon, last_logoff, account_expires, max_storage, units_per_week;
            internal IntPtr logon_hours;
            internal uint bad_password_count, number_logons;
            internal IntPtr logon_server;
            internal uint country_code, code_page;
        }
        [StructLayout(LayoutKind.Sequential)]
        internal struct USER_INFO_23
        { internal IntPtr name, full_name, comment; internal uint flags; internal IntPtr sid; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct LOCALGROUP_MEMBERS_INFO_0 { internal IntPtr sid; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct SID_AND_ATTRIBUTES { internal IntPtr sid; internal uint attributes; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct TOKEN_GROUPS_HEADER { internal uint count; internal SID_AND_ATTRIBUTES first; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct LUID { internal uint low; internal int high; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct LUID_AND_ATTRIBUTES { internal LUID luid; internal uint attributes; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct LSA_OBJECT_ATTRIBUTES
        { internal uint length; internal IntPtr root, name; internal uint attributes; internal IntPtr security, quality; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct LSA_UNICODE_STRING { internal ushort length, maximum; internal IntPtr buffer; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct FILE_INFO
        {
            internal uint attributes; internal System.Runtime.InteropServices.ComTypes.FILETIME creation, access, write;
            internal uint volume, sizeHigh, sizeLow, links, indexHigh, indexLow;
        }
        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
        internal static extern uint NetUserAdd(string servername, uint level, ref USER_INFO_1 user, out uint parameter);
        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
        internal static extern uint NetUserGetInfo(string servername, string username, uint level, out IntPtr buffer);
        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
        internal static extern uint NetUserEnum(string servername, uint level, uint filter, out IntPtr buffer, uint preferred, out uint entries, out uint total, ref uint resume);
        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
        internal static extern uint NetUserGetLocalGroups(string servername, string username, uint level, uint flags, out IntPtr buffer, uint preferred, out uint entries, out uint total);
        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
        internal static extern uint NetLocalGroupAddMembers(string servername, string groupname, uint level, ref LOCALGROUP_MEMBERS_INFO_0 member, uint total);
        [DllImport("Netapi32.dll", ExactSpelling = true)] internal static extern uint NetApiBufferFree(IntPtr buffer);
        [DllImport("Netapi32.dll", ExactSpelling = true)] internal static extern uint NetApiBufferSize(IntPtr buffer, out uint bytes);
        [DllImport("Advapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool LookupAccountSidW(string system, IntPtr sid, StringBuilder name, ref uint nameSize, StringBuilder domain, ref uint domainSize, out uint type);
        [DllImport("Advapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool LookupAccountNameW(string system, string name, IntPtr sid, ref uint sidSize, StringBuilder domain, ref uint domainSize, out uint type);
        [DllImport("Advapi32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
        [DllImport("Advapi32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool OpenThreadToken(IntPtr thread, uint access, [MarshalAs(UnmanagedType.Bool)] bool openAsSelf, out IntPtr token);
        [DllImport("Advapi32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetTokenInformation(IntPtr token, uint information, IntPtr buffer, uint length, out uint returned);
        [DllImport("Advapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool LookupPrivilegeNameW(string system, ref LUID luid, StringBuilder name, ref uint size);
        [DllImport("Advapi32.dll", ExactSpelling = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool IsValidSid(IntPtr sid);
        [DllImport("Advapi32.dll", ExactSpelling = true)] internal static extern uint GetLengthSid(IntPtr sid);
        [DllImport("Advapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool ConvertSidToStringSidW(IntPtr sid, out IntPtr text);
        [DllImport("Kernel32.dll", ExactSpelling = true)] internal static extern IntPtr GetCurrentProcess();
        [DllImport("Kernel32.dll", ExactSpelling = true)] internal static extern IntPtr GetCurrentThread();
        [DllImport("Kernel32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CloseHandle(IntPtr handle);
        [DllImport("Kernel32.dll", ExactSpelling = true)] internal static extern IntPtr LocalFree(IntPtr allocation);
        [DllImport("Kernel32.dll", ExactSpelling = true, SetLastError = true)] internal static extern UIntPtr LocalSize(IntPtr allocation);
        [DllImport("Advapi32.dll", ExactSpelling = true)] internal static extern uint LsaOpenPolicy(IntPtr system, ref LSA_OBJECT_ATTRIBUTES attributes, uint access, out IntPtr policy);
        [DllImport("Advapi32.dll", ExactSpelling = true)] internal static extern uint LsaEnumerateAccountRights(IntPtr policy, IntPtr sid, out IntPtr rights, out uint count);
        [DllImport("Advapi32.dll", ExactSpelling = true)] internal static extern uint LsaFreeMemory(IntPtr memory);
        [DllImport("Advapi32.dll", ExactSpelling = true)] internal static extern uint LsaClose(IntPtr policy);
        [DllImport("Kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        internal static extern uint GetFileAttributesW(string path);
        [DllImport("Kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CreateDirectoryW(string path, IntPtr security);
        [DllImport("Kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        internal static extern IntPtr CreateFileW(string path, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
        [DllImport("Kernel32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetFileInformationByHandle(IntPtr handle, out FILE_INFO info);
        [DllImport("Advapi32.dll", ExactSpelling = true)]
        internal static extern uint GetSecurityInfo(IntPtr handle, uint type, uint information, out IntPtr owner, out IntPtr group, out IntPtr dacl, out IntPtr sacl, out IntPtr descriptor);
        [DllImport("Advapi32.dll", ExactSpelling = true)] internal static extern uint GetSecurityDescriptorLength(IntPtr descriptor);
        [StructLayout(LayoutKind.Sequential)]
        internal struct MEMORY_INFO
        { internal IntPtr address, allocation; internal uint allocationProtect; internal UIntPtr size; internal uint state, protect, type; }
        [DllImport("Kernel32.dll", ExactSpelling = true)] internal static extern UIntPtr VirtualQuery(IntPtr address, out MEMORY_INFO information, UIntPtr length);
    }

    internal sealed class Owned : IDisposable
    {
        internal IntPtr Pointer { get; private set; }
        internal readonly uint Length;
        private Action<IntPtr> release;
        internal Owned(IntPtr p, uint size, Action<IntPtr> free) { Pointer = p; Length = size; release = free; }
        internal static Owned Allocate(uint size)
        { Gate.Check(size > 0 && size <= 16777216, "BUFFER_SIZE"); return new Owned(Marshal.AllocHGlobal(checked((int)size)), size, Marshal.FreeHGlobal); }
        internal static Owned Net(IntPtr p)
        {
            if (p == IntPtr.Zero) return new Owned(p, 0, null);
            uint size;
            try { Gate.Check(Native.NetApiBufferSize(p, out size) == 0 && size > 0 && size <= 16777216, "NET_BUFFER_SIZE"); }
            catch { Gate.Check(Native.NetApiBufferFree(p) == 0, "NET_BUFFER_RELEASE"); throw; }
            return new Owned(p, size, delegate(IntPtr v) { Gate.Check(Native.NetApiBufferFree(v) == 0, "NET_BUFFER_RELEASE"); });
        }
        internal void Range(IntPtr p, ulong length)
        {
            ulong start = unchecked((ulong)Pointer.ToInt64()), at = unchecked((ulong)p.ToInt64());
            Gate.Check(Pointer != IntPtr.Zero && at >= start && length <= Length && at - start <= Length - length, "BUFFER_BOUNDS");
        }
        internal T Structure<T>(IntPtr p) where T : struct
        { Range(p, (ulong)Marshal.SizeOf(typeof(T))); return (T)Marshal.PtrToStructure(p, typeof(T)); }
        internal uint U32(int offset) { IntPtr p = IntPtr.Add(Pointer, offset); Range(p, 4); return unchecked((uint)Marshal.ReadInt32(p)); }
        internal string Text(IntPtr p, bool nullable)
        {
            if (p == IntPtr.Zero) { Gate.Check(nullable, "NULL_TEXT"); return null; }
            Gate.Check((p.ToInt64() & 1) == 0, "UTF16_ALIGNMENT"); var chars = new List<char>();
            for (int i = 0; i <= 32768; i++)
            {
                IntPtr c = IntPtr.Add(p, checked(i * 2)); Range(c, 2); char value = (char)Marshal.ReadInt16(c);
                if (value == '\0') { string result = new string(chars.ToArray()); new UnicodeEncoding(false, false, true).GetBytes(result); return result; }
                chars.Add(value);
            }
            throw new CeremonyException("TEXT_SIZE", false);
        }
        internal string Sid(IntPtr p)
        {
            Range(p, 8); Gate.Check(Marshal.ReadByte(p) == 1, "SID_REVISION"); int count = Marshal.ReadByte(p, 1);
            Gate.Check(count >= 1 && count <= 15, "SID_COUNT"); uint size = checked((uint)(8 + count * 4)); Range(p, size);
            Gate.Check(Native.IsValidSid(p) && Native.GetLengthSid(p) == size, "WINDOWS_SID");
            byte[] raw = new byte[size]; Marshal.Copy(p, raw, 0, checked((int)size)); string sid = new SecurityIdentifier(raw, 0).Value;
            J.Sid(sid); IntPtr text = IntPtr.Zero;
            try
            {
                Gate.Check(Native.ConvertSidToStringSidW(p, out text) && text != IntPtr.Zero, "SID_CONVERT");
                ulong allocated = Native.LocalSize(text).ToUInt64(); Gate.Check(allocated > 0 && allocated <= 4096, "SID_TEXT_SIZE");
                using (var view = new Owned(text, (uint)allocated, null)) J.Eq(view.Text(text, false), sid);
            }
            finally { if (text != IntPtr.Zero) Gate.Check(Native.LocalFree(text) == IntPtr.Zero, "LOCAL_RELEASE"); }
            return sid;
        }
        public void Dispose()
        { Action<IntPtr> r = release; IntPtr p = Pointer; release = null; Pointer = IntPtr.Zero; if (r != null && p != IntPtr.Zero) r(p); }
    }

    internal sealed class WindowsAdapter : IReadAdapter, IDisposable
    {
        private bool createConsumed, usersConsumed;
        internal WindowsAdapter() { Gate.Require(); Host(); }
        private static void Host()
        { Gate.Check(Environment.Is64BitProcess && Environment.OSVersion.Platform == PlatformID.Win32NT && Environment.MachineName == Launcher.HOST, "HOST"); }
        public void Dispose() { }
        public uint AbsenceStatus()
        {
            IntPtr p = IntPtr.Zero; uint status = Native.NetUserGetInfo(null, Launcher.CANDIDATE_NAME, 1, out p);
            using (Owned b = Owned.Net(p)) Gate.Check(status != 2221 || p == IntPtr.Zero, "ABSENCE_BUFFER");
            return status;
        }
        public EnumPage UsersPage(uint resume)
        {
            IntPtr p = IntPtr.Zero; uint entries, total;
            uint status = Native.NetUserEnum(null, 0, 0, out p, UInt32.MaxValue, out entries, out total, ref resume);
            Owned b = Owned.Net(p);
            try
            {
                Gate.Check(status == 0 || status == 234, "ENUM_STATUS");
                var names = Names(b, entries);
                return new EnumPage(status, entries, total, resume, names, b.Dispose);
            }
            catch { b.Dispose(); throw; }
        }
        private static List<string> Names(Owned b, uint entries)
        {
            var names = new List<string>();
            if (entries > 0) b.Range(b.Pointer, checked((ulong)entries * (ulong)IntPtr.Size));
            for (uint i = 0; i < entries; i++)
            { string name = b.Text(Marshal.ReadIntPtr(b.Pointer, checked((int)i * IntPtr.Size)), false); Proof.Name(name); names.Add(name); }
            return names;
        }
        private static Owned SidBytes(string sid)
        {
            J.Sid(sid); var identity = new SecurityIdentifier(sid); byte[] bytes = new byte[identity.BinaryLength]; identity.GetBinaryForm(bytes, 0);
            Owned b = Owned.Allocate((uint)bytes.Length); Marshal.Copy(bytes, 0, b.Pointer, bytes.Length); return b;
        }
        internal static Dictionary<string, object> ResolveSid(string sid)
        {
            using (Owned raw = SidBytes(sid))
            {
                uint nc = 0, dc = 0, type;
                bool ok = Native.LookupAccountSidW(null, raw.Pointer, null, ref nc, null, ref dc, out type); int error = Marshal.GetLastWin32Error();
                Gate.Check(!ok && error == 122 && nc > 1 && nc <= 32768 && dc > 0 && dc <= 32768, "SID_LOOKUP_PROBE");
                uint ncap = nc, dcap = dc; var name = new StringBuilder((int)nc); var domain = new StringBuilder((int)dc);
                Gate.Check(Native.LookupAccountSidW(null, raw.Pointer, name, ref nc, domain, ref dc, out type) && nc < ncap && dc < dcap && nc == name.Length && dc == domain.Length, "SID_LOOKUP");
                Proof.Name(name.ToString()); J.Text(domain.ToString());
                return J.O("sid", sid, "resolved_name", name.ToString(), "domain", domain.ToString(), "sid_type", (ulong)type, "roundtrip_passed", false);
            }
        }
        internal static Dictionary<string, object> ResolveName(string qualified)
        {
            uint size = 0, dc = 0, type;
            bool ok = Native.LookupAccountNameW(null, qualified, IntPtr.Zero, ref size, null, ref dc, out type); int error = Marshal.GetLastWin32Error();
            Gate.Check(!ok && error == 122 && size >= 12 && size <= 68 && dc > 0 && dc <= 32768, "NAME_LOOKUP_PROBE");
            uint originalSize = size, capacity = dc; using (Owned b = Owned.Allocate(size))
            {
                var domain = new StringBuilder((int)dc);
                Gate.Check(Native.LookupAccountNameW(null, qualified, b.Pointer, ref size, domain, ref dc, out type) && size == originalSize && dc < capacity && dc == domain.Length, "NAME_LOOKUP");
                string sid = b.Sid(b.Pointer); var reverse = ResolveSid(sid);
                J.Eq(reverse["domain"], domain.ToString()); J.Eq(reverse["sid_type"], (ulong)type);
                J.Eq(J.S(reverse["domain"]) + "\\" + J.S(reverse["resolved_name"]), qualified);
                reverse["roundtrip_passed"] = true; return reverse;
            }
        }
        public Dictionary<string, object> UsersIdentity()
        {
            var reverse = ResolveSid(Launcher.BUILTIN_USERS_SID);
            var result = ResolveName(J.S(reverse["domain"]) + "\\" + J.S(reverse["resolved_name"])); Proof.Identity(result);
            using (var ps = PowerShell.Create(System.Management.Automation.RunspaceMode.CurrentRunspace))
            {
                ps.AddCommand("Microsoft.PowerShell.LocalAccounts\\Get-LocalGroup").AddParameter("SID", new SecurityIdentifier(Launcher.BUILTIN_USERS_SID)).AddParameter("ErrorAction", "Stop");
                var rows = ps.Invoke(); Gate.Check(!ps.HadErrors && rows.Count == 1, "USERS_INVENTORY");
                J.Eq(PropertySid(rows[0], "SID"), Launcher.BUILTIN_USERS_SID); J.Eq(PropertyString(rows[0], "Name"), result["resolved_name"]);
            }
            return result;
        }
        private static string Empty(string value) { return String.IsNullOrEmpty(value) ? null : value; }
        private Dictionary<string, object> Level23()
        {
            IntPtr p = IntPtr.Zero; uint status = Native.NetUserGetInfo(null, Launcher.CANDIDATE_NAME, 23, out p);
            using (Owned b = Owned.Net(p))
            {
                Gate.Check(status == 0, "ACCOUNT23_STATUS"); var u = b.Structure<Native.USER_INFO_23>(p);
                J.Eq(b.Text(u.name, false), Launcher.CANDIDATE_NAME); J.Eq(Empty(b.Text(u.full_name, true)), null); J.Eq(b.Text(u.comment, false), Gate.Comment);
                J.Eq((ulong)u.flags, 0x201UL); string sid = b.Sid(u.sid); J.CandidateSid(sid);
                return J.O("sid", sid, "flags", (ulong)u.flags);
            }
        }
        public Dictionary<string, object> Account()
        {
            IntPtr p = IntPtr.Zero; uint status = Native.NetUserGetInfo(null, Launcher.CANDIDATE_NAME, 2, out p);
            using (Owned b = Owned.Net(p))
            {
                Gate.Check(status == 0, "ACCOUNT2_STATUS"); var u = b.Structure<Native.USER_INFO_2>(p);
                // Never dereference the queried password member, even if malformed.
                Gate.Check(u.password == IntPtr.Zero, "ACCOUNT_PASSWORD_MEMBER");
                J.Eq(b.Text(u.name, false), Launcher.CANDIDATE_NAME); J.Eq((ulong)u.privilege, 1UL); J.Eq((ulong)u.flags, 0x201UL);
                J.Eq(b.Text(u.comment, false), Gate.Comment);
                foreach (IntPtr s in new[] { u.home_dir, u.script_path, u.full_name, u.user_comment, u.parameters, u.workstations }) J.Eq(Empty(b.Text(s, true)), null);
                Gate.Check(u.auth_flags == 0 && u.account_expires == UInt32.MaxValue && u.max_storage == UInt32.MaxValue && u.country_code == 0 && u.code_page == 0, "ACCOUNT_DEFAULTS");
                J.Eq(b.Text(u.logon_server, false), @"\\*");
                Gate.Check(u.units_per_week > 0 && u.units_per_week <= 10080 && u.units_per_week % 8 == 0, "LOGON_HOURS");
                uint length = u.units_per_week / 8; b.Range(u.logon_hours, length);
                for (int i = 0; i < length; i++) Gate.Check(Marshal.ReadByte(u.logon_hours, i) == 255, "LOGON_HOURS");
            }
            var first = Level23(); string sidValue = J.S(first["sid"]);
            var reverse = ResolveSid(sidValue); J.Eq(reverse["domain"], Launcher.HOST); J.Eq(reverse["resolved_name"], Launcher.CANDIDATE_NAME); J.Eq(reverse["sid_type"], 1UL);
            var mapped = ResolveName(Launcher.HOST + "\\" + Launcher.CANDIDATE_NAME); J.Eq(mapped["sid"], sidValue); J.Eq(mapped["sid_type"], 1UL);
            Gate.Check(J.Bytes(first).SequenceEqual(J.Bytes(Level23())), "ACCOUNT_DRIFT");
            var result = J.O("name", Launcher.CANDIDATE_NAME, "sid", sidValue, "enabled", true, "privilege", 1UL, "flags", 0x201UL,
                "machine_domain_sid", Gate.MachineSid, "comment", Gate.Comment, "full_name", null, "account_expires", (ulong)UInt32.MaxValue,
                "defaults_readback_passed", true, "bidirectional_mapping_passed", true);
            Proof.Account(result); return result;
        }
        public Dictionary<string, object> Groups(uint flags)
        {
            Gate.Check(flags <= 1, "GROUP_FLAGS"); IntPtr p = IntPtr.Zero; uint entries, total;
            uint status = Native.NetUserGetLocalGroups(null, Launcher.CANDIDATE_NAME, 0, flags, out p, UInt32.MaxValue, out entries, out total);
            var groups = J.A();
            using (Owned b = Owned.Net(p))
            {
                Gate.Check(status == 0 && entries == total, "GROUP_STATUS_OR_COUNT");
                foreach (string name in Names(b, entries))
                {
                    var identity = ResolveNameForLocalGroup(name);
                    groups.Add(J.O("sid", identity["sid"], "name", name));
                }
            }
            Proof.Sort(groups, "sid name");
            var result = J.O("flags", (ulong)flags, "level", 0UL, "status", 0UL, "entries_read", (ulong)entries, "total_entries", (ulong)total, "groups", groups);
            Proof.Groups(result, flags); return result;
        }
        private static Dictionary<string, object> ResolveNameForLocalGroup(string name)
        {
            // A complete SID-addressed inventory avoids name/domain guessing and
            // ambiguous fallback lookups for localized builtin aliases.
            using (var ps = PowerShell.Create(System.Management.Automation.RunspaceMode.CurrentRunspace))
            {
                ps.AddCommand("Microsoft.PowerShell.LocalAccounts\\Get-LocalGroup").AddParameter("ErrorAction", "Stop");
                var rows = ps.Invoke(); Gate.Check(!ps.HadErrors, "GROUP_INVENTORY");
                var matches = rows.Where(r => PropertyString(r, "Name") == name).ToList(); Gate.Check(matches.Count == 1, "GROUP_MAPPING");
                string sid = PropertySid(matches[0], "SID"); var reverse = ResolveSid(sid);
                Gate.Check(J.S(reverse["domain"]) == "BUILTIN" || J.S(reverse["domain"]) == Launcher.HOST, "LOCAL_GROUP_DOMAIN");
                var mapped = ResolveName(J.S(reverse["domain"]) + "\\" + name); J.Eq(mapped["sid"], sid); J.Eq(mapped["sid_type"], 4UL); return mapped;
            }
        }
        internal static string PropertyString(PSObject value, string property)
        { Gate.Check(value.Properties[property] != null && value.Properties[property].Value is string, "INVENTORY_PROPERTY"); return (string)value.Properties[property].Value; }
        internal static string PropertySid(PSObject value, string property)
        { Gate.Check(value.Properties[property] != null && value.Properties[property].Value is SecurityIdentifier, "INVENTORY_SID"); string sid = ((SecurityIdentifier)value.Properties[property].Value).Value; J.Sid(sid); return sid; }
        private static void NoThreadToken()
        {
            IntPtr token = IntPtr.Zero; bool ok = Native.OpenThreadToken(Native.GetCurrentThread(), 8, true, out token); int error = Marshal.GetLastWin32Error();
            if (token != IntPtr.Zero) Gate.Check(Native.CloseHandle(token), "THREAD_TOKEN_RELEASE");
            Gate.Check(!ok && token == IntPtr.Zero && error == 1008, "THREAD_IMPERSONATION");
        }
        private static Owned TokenBuffer(IntPtr token, uint information)
        {
            uint size; bool ok = Native.GetTokenInformation(token, information, IntPtr.Zero, 0, out size); int error = Marshal.GetLastWin32Error();
            Gate.Check(!ok && error == 122, "TOKEN_PROBE"); Owned b = Owned.Allocate(size);
            try { uint returned; Gate.Check(Native.GetTokenInformation(token, information, b.Pointer, size, out returned) && returned == size, "TOKEN_READ"); return b; }
            catch { b.Dispose(); throw; }
        }
        private static uint TokenDword(IntPtr token, uint information)
        { using (Owned b = TokenBuffer(token, information)) { Gate.Check(b.Length == 4, "TOKEN_DWORD"); return b.U32(0); } }
        public Dictionary<string, object> Token()
        {
            Host(); NoThreadToken(); IntPtr token = IntPtr.Zero;
            try
            {
                Gate.Check(Native.OpenProcessToken(Native.GetCurrentProcess(), 8, out token) && token != IntPtr.Zero, "PROCESS_TOKEN");
                uint type = TokenDword(token, 8), elevated = TokenDword(token, 20), elevationType = TokenDword(token, 18);
                Gate.Check(elevated <= 1, "TOKEN_BOOLEAN"); string sid;
                using (Owned b = TokenBuffer(token, 1)) { var u = b.Structure<Native.SID_AND_ATTRIBUTES>(b.Pointer); sid = b.Sid(u.sid); }
                var groups = J.A();
                using (Owned b = TokenBuffer(token, 2))
                {
                    uint count = b.U32(0); int offset = (int)Marshal.OffsetOf(typeof(Native.TOKEN_GROUPS_HEADER), "first"); int stride = Marshal.SizeOf(typeof(Native.SID_AND_ATTRIBUTES));
                    b.Range(IntPtr.Add(b.Pointer, offset), checked((ulong)count * (ulong)stride));
                    for (int i = 0; i < count; i++)
                    {
                        var g = b.Structure<Native.SID_AND_ATTRIBUTES>(IntPtr.Add(b.Pointer, checked(offset + i * stride))); string gs = b.Sid(g.sid);
                        // Some OS session/integrity SIDs are not name-mapped. Their
                        // canonical public SID is an explicit display fallback only.
                        string display = gs;
                        if (Proof.Classification(gs) == "BASELINE" || Proof.Classification(gs) == "HOST_DYNAMIC_BASELINE" || Proof.Classification(gs) == "UNKNOWN")
                        { var identity = ResolveSid(gs); display = J.S(identity["domain"]) + "\\" + J.S(identity["resolved_name"]); }
                        groups.Add(J.O("sid", gs, "name", display, "attributes", (ulong)g.attributes, "classification", Proof.Classification(gs)));
                    }
                }
                var privileges = J.A();
                using (Owned b = TokenBuffer(token, 3))
                {
                    uint count = b.U32(0); int stride = Marshal.SizeOf(typeof(Native.LUID_AND_ATTRIBUTES));
                    b.Range(IntPtr.Add(b.Pointer, 4), checked((ulong)count * (ulong)stride));
                    for (int i = 0; i < count; i++)
                    {
                        var p = b.Structure<Native.LUID_AND_ATTRIBUTES>(IntPtr.Add(b.Pointer, checked(4 + i * stride))); uint size = 0;
                        bool ok = Native.LookupPrivilegeNameW(null, ref p.luid, null, ref size); int error = Marshal.GetLastWin32Error();
                        Gate.Check(!ok && error == 122 && size > 0 && size < 32768, "PRIVILEGE_PROBE");
                        uint capacity = size + 1; size = capacity; var name = new StringBuilder((int)capacity);
                        Gate.Check(Native.LookupPrivilegeNameW(null, ref p.luid, name, ref size) && size == name.Length && size < capacity, "PRIVILEGE_NAME");
                        privileges.Add(J.O("name", name.ToString(), "attributes", (ulong)p.attributes, "enabled", (p.attributes & 2) != 0,
                            "enabled_by_default", (p.attributes & 1) != 0, "removed", (p.attributes & 4) != 0, "disposition", Proof.PrivilegeDisposition(name.ToString())));
                    }
                }
                Proof.Sort(groups, "sid name"); Proof.Sort(privileges, "name");
                var admin = groups.SingleOrDefault(g => J.S(J.Obj(g)["sid"]) == Gate.Administrators);
                var result = J.O("user_sid", sid, "token_type", (ulong)type, "elevated", elevated == 1, "elevation_type", (ulong)elevationType,
                    "administrators_present", admin != null, "administrators_enabled", admin != null && (J.N(J.Obj(admin)["attributes"]) & 4) != 0,
                    "administrators_deny_only", admin != null && (J.N(J.Obj(admin)["attributes"]) & 16) != 0, "thread_token_absent", true, "groups", groups, "privileges", privileges);
                var actorMapping = ResolveSid(sid); J.Eq(actorMapping["domain"], Launcher.HOST); J.Eq(actorMapping["sid_type"], 1UL);
                var actorRoundtrip = ResolveName(Launcher.HOST + "\\" + J.S(actorMapping["resolved_name"])); J.Eq(actorRoundtrip["sid"], sid);
                J.Eq(sid.Substring(0, sid.LastIndexOf('-')), Gate.MachineSid);
                NoThreadToken(); Proof.TokenShape(result); return result;
            }
            finally { if (token != IntPtr.Zero) Gate.Check(Native.CloseHandle(token), "PROCESS_TOKEN_RELEASE"); }
        }
        internal static Native.USER_INFO_1 FrozenUser(IntPtr password)
        {
            return new Native.USER_INFO_1 { name = Launcher.CANDIDATE_NAME, password = password, password_age = 0,
                privilege = 1, home_dir = null, comment = Gate.Comment, flags = 1, script_path = null };
        }
        internal sealed class CreateResult
        {
            internal readonly uint Status;
            internal readonly uint? Parameter;
            internal CreateResult(uint status, uint? parameter) { Status = status; Parameter = parameter; }
        }
        internal CreateResult CreateAccount(SecureString secret, Journal journal)
        {
            Gate.Require(); // Must precede even secret validation/marshal.
            Gate.Check(!createConsumed, "CREATE_CONSUMED"); createConsumed = true;
            Gate.Check(secret != null, "SECURE_INPUT_INVALID");
            IntPtr password = IntPtr.Zero; bool dispatched = false; uint status = UInt32.MaxValue;
            try
            {
                // Only emptiness is inspected; length is never retained or output.
                Gate.Check(secret.Length != 0, "SECURE_INPUT_INVALID");
                Proof.Creator(Token());
                journal.BeginDispatch("ACCOUNT_CREATION_ATTEMPTED");
                password = Marshal.SecureStringToGlobalAllocUnicode(secret);
                Gate.Check(password != IntPtr.Zero, "SECURE_MARSHAL");
                var user = FrozenUser(password); uint parameter = 0;
                dispatched = true;
                status = Native.NetUserAdd(null, 1, ref user, out parameter);
                // USER_INFO_1 never escapes this stack frame or becomes evidence.
                user.password = IntPtr.Zero;
                return new CreateResult(status, status == 87 && parameter >= 1 && parameter <= 8 ? (uint?)parameter : null);
            }
            catch { throw new CeremonyException("CREATE_UNCERTAIN", dispatched); }
            finally
            {
                try { if (password != IntPtr.Zero) Marshal.ZeroFreeGlobalAllocUnicode(password); }
                catch { throw new CeremonyException("PASSWORD_RELEASE_UNCERTAIN", dispatched); }
                finally
                {
                    password = IntPtr.Zero;
                    try { if (secret != null) secret.Dispose(); }
                    catch { throw new CeremonyException("SECURESTRING_RELEASE_UNCERTAIN", dispatched); }
                    finally { secret = null; }
                }
            }
        }
        internal uint AssignUsers(string retainedSid, string revalidatedName, Journal journal)
        {
            Gate.Require(); Gate.Check(!usersConsumed, "USERS_CONSUMED"); usersConsumed = true;
            J.CandidateSid(retainedSid); var account = Account(); J.Eq(account["sid"], retainedSid);
            var identity = UsersIdentity(); J.Eq(identity["resolved_name"], revalidatedName); Proof.Creator(Token());
            Gate.Check(Proof.Groups(Groups(0), 0).Count == 0, "USERS_NOT_EMPTY");
            using (Owned b = SidBytes(retainedSid))
            {
                var member = new Native.LOCALGROUP_MEMBERS_INFO_0 { sid = b.Pointer };
                journal.BeginDispatch("USERS_ASSIGNMENT_ATTEMPTED");
                return Native.NetLocalGroupAddMembers(null, revalidatedName, 0, ref member, 1);
            }
        }
        internal List<object> Inventory(string candidateSid)
        {
            var edges = J.A(); var groups = new Dictionary<string, string>(StringComparer.Ordinal);
            using (var ps = PowerShell.Create(System.Management.Automation.RunspaceMode.CurrentRunspace))
            {
                ps.AddCommand("Microsoft.PowerShell.LocalAccounts\\Get-LocalGroup").AddParameter("ErrorAction", "Stop");
                var rows = ps.Invoke(); Gate.Check(!ps.HadErrors && rows.Count > 0, "GROUP_INVENTORY");
                foreach (PSObject row in rows)
                {
                    string sid = PropertySid(row, "SID"), name = PropertyString(row, "Name"); Proof.Name(name);
                    Gate.Check(!groups.ContainsKey(sid) && !groups.Values.Contains(name, StringComparer.OrdinalIgnoreCase), "GROUP_INVENTORY_DUPLICATE");
                    var mapping = ResolveSid(sid); J.Eq(mapping["resolved_name"], name); J.Eq(mapping["sid_type"], 4UL);
                    Gate.Check(J.S(mapping["domain"]) == "BUILTIN" || J.S(mapping["domain"]) == Launcher.HOST, "GROUP_INVENTORY_DOMAIN"); groups.Add(sid, name);
                }
            }
            foreach (var group in groups)
            {
                using (var ps = PowerShell.Create(System.Management.Automation.RunspaceMode.CurrentRunspace))
                {
                    ps.AddCommand("Microsoft.PowerShell.LocalAccounts\\Get-LocalGroupMember").AddParameter("SID", new SecurityIdentifier(group.Key)).AddParameter("ErrorAction", "Stop");
                    var members = ps.Invoke(); Gate.Check(!ps.HadErrors, "GROUP_MEMBER_INVENTORY");
                    foreach (PSObject member in members)
                    {
                        string sid = PropertySid(member, "SID"); string name = PropertyString(member, "Name"); J.Text(name);
                        var resolved = ResolveSid(sid); var roundtrip = ResolveName(J.S(resolved["domain"]) + "\\" + J.S(resolved["resolved_name"])); J.Eq(roundtrip["sid"], sid);
                        edges.Add(J.O("member_sid", sid, "group_sid", group.Key, "origin", sid == candidateSid ? "DIRECT" : groups.ContainsKey(sid) ? "NESTED" : "LOGON_CONTEXT"));
                    }
                }
            }
            Proof.Sort(edges, "member_sid group_sid origin");
            // Every group is queried, including forbidden and unrelated groups.
            Qualification.Reach(groups.Keys, edges, false); return edges;
        }
        private static void Readable(IntPtr address, ulong bytes)
        {
            Gate.Check(address != IntPtr.Zero && bytes > 0 && bytes <= 16777216, "LSA_BOUNDS");
            ulong current = unchecked((ulong)address.ToInt64()), remaining = bytes;
            while (remaining > 0)
            {
                Native.MEMORY_INFO info;
                Gate.Check(Native.VirtualQuery(new IntPtr(unchecked((long)current)), out info, (UIntPtr)(uint)Marshal.SizeOf(typeof(Native.MEMORY_INFO))).ToUInt64() == (ulong)Marshal.SizeOf(typeof(Native.MEMORY_INFO)), "LSA_MEMORY_QUERY");
                ulong start = unchecked((ulong)info.address.ToInt64()), size = info.size.ToUInt64();
                Gate.Check(info.state == 0x1000 && (info.protect & 0x101) == 0 && (info.protect & 0xEE) != 0 && current >= start && current - start < size, "LSA_MEMORY_RANGE");
                ulong available = size - (current - start), step = Math.Min(available, remaining);
                current = checked(current + step); remaining -= step;
            }
        }
        internal List<object> Rights(string candidateSid, IEnumerable<string> effectiveSids)
        {
            IntPtr policy = IntPtr.Zero;
            var attributes = new Native.LSA_OBJECT_ATTRIBUTES { length = (uint)Marshal.SizeOf(typeof(Native.LSA_OBJECT_ATTRIBUTES)) };
            var rights = J.A();
            try
            {
                Gate.Check(Native.LsaOpenPolicy(IntPtr.Zero, ref attributes, 0x800, out policy) == 0 && policy != IntPtr.Zero, "LSA_POLICY");
                foreach (string sid in effectiveSids.Concat(new[] { candidateSid }).Distinct(StringComparer.Ordinal).OrderBy(x => x, StringComparer.Ordinal))
                {
                    using (Owned principal = SidBytes(sid))
                    {
                        IntPtr p = IntPtr.Zero; uint count;
                        uint status = Native.LsaEnumerateAccountRights(policy, principal.Pointer, out p, out count);
                        try
                        {
                            // STATUS_OBJECT_NAME_NOT_FOUND: this SID has no policy
                            // account/assigned rights. Other errors never mean none.
                            if (status == 0xC0000034) { Gate.Check(p == IntPtr.Zero && count == 0, "LSA_EMPTY"); continue; }
                            Gate.Check(status == 0 && count <= 65536, "LSA_RIGHTS");
                            int stride = Marshal.SizeOf(typeof(Native.LSA_UNICODE_STRING));
                            if (count > 0) Readable(p, checked((ulong)count * (ulong)stride));
                            using (var view = new Owned(p, checked(count * (uint)stride), null))
                            {
                                for (int i = 0; i < count; i++)
                                {
                                    var text = view.Structure<Native.LSA_UNICODE_STRING>(IntPtr.Add(p, checked(i * stride)));
                                    Gate.Check(text.length > 0 && text.length % 2 == 0 && text.length <= text.maximum, "LSA_STRING"); Readable(text.buffer, text.length);
                                    byte[] bytes = new byte[text.length]; Marshal.Copy(text.buffer, bytes, 0, bytes.Length);
                                    string name = new UnicodeEncoding(false, false, true).GetString(bytes); J.Text(name);
                                    rights.Add(J.O("principal_sid", sid, "name", name, "origin", sid == candidateSid ? "DIRECT" : "NESTED", "disposition", Qualification.RightDisposition(name)));
                                }
                            }
                        }
                        finally { if (p != IntPtr.Zero) Gate.Check(Native.LsaFreeMemory(p) == 0, "LSA_MEMORY_RELEASE"); }
                    }
                }
            }
            finally { if (policy != IntPtr.Zero) Gate.Check(Native.LsaClose(policy) == 0, "LSA_POLICY_RELEASE"); }
            Proof.Sort(rights, "principal_sid name origin"); return rights;
        }
        internal Dictionary<string, object> Observation()
        {
            var account = Account(); string sid = J.S(account["sid"]); var token = Token();
            J.Eq(token["user_sid"], sid); var direct = Groups(0); var indirect = Groups(1); var edges = Inventory(sid);
            var tokenGroups = J.Arr(token["groups"]); var effective = J.A(); var directSids = Proof.Groups(direct, 0);
            foreach (object v in tokenGroups)
            {
                var g = J.Obj(v); string gs = J.S(g["sid"]);
                effective.Add(J.O("sid", gs, "name", g["name"], "attributes", g["attributes"], "origin", directSids.Contains(gs) ? "DIRECT" : "LOGON_CONTEXT",
                    "disposition", Proof.Classification(gs) == "UNKNOWN" ? "UNRESOLVED" : "ACCEPTED"));
            }
            var seeds = tokenGroups.Where(v => (J.N(J.Obj(v)["attributes"]) & 20) == 4 && J.S(J.Obj(v)["sid"]) != Launcher.PERFORMANCE_LOG_USERS_SID).Select(v => J.S(J.Obj(v)["sid"]));
            bool alternate = Qualification.Reach(seeds.Concat(new[] { sid }), edges, true).Contains(Launcher.PERFORMANCE_LOG_USERS_SID);
            bool interactive = tokenGroups.Any(v => J.S(J.Obj(v)["sid"]) == Gate.Interactive && (J.N(J.Obj(v)["attributes"]) & 20) == 4);
            bool present = tokenGroups.Any(v => J.S(J.Obj(v)["sid"]) == Launcher.PERFORMANCE_LOG_USERS_SID);
            bool edge = edges.Any(v => J.S(J.Obj(v)["member_sid"]) == Gate.Interactive && J.S(J.Obj(v)["group_sid"]) == Launcher.PERFORMANCE_LOG_USERS_SID);
            var performance = J.O("classification", Gate.PerformanceClass, "effective", present, "direct_assignment", directSids.Contains(Launcher.PERFORMANCE_LOG_USERS_SID),
                "interactive_enabled", interactive, "host_edge_present", edge, "alternate_path_present", alternate,
                "provenance_passed", !alternate && interactive && (!present || edge) && directSids.SetEquals(new[] { Launcher.BUILTIN_USERS_SID }));
            var observation = J.O("account", account, "direct_view", direct, "indirect_view", indirect, "relevant_edges", edges, "effective_groups", effective,
                "rights", Rights(sid, tokenGroups.Select(v => J.S(J.Obj(v)["sid"]))), "candidate_token", token,
                "collection_method", "operator_observed_console", "performance_log_users", performance);
            J.Eq(Account()["sid"], sid); Gate.Check(J.Bytes(direct).SequenceEqual(J.Bytes(Groups(0))) && J.Bytes(indirect).SequenceEqual(J.Bytes(Groups(1))), "GROUP_DRIFT");
            Qualification.Shape(observation); return observation;
        }
    }

    internal sealed class DirectoryGuard : IDisposable
    {
        private readonly string path;
        private readonly Owned handle;
        private readonly Dictionary<string, object> identity;
        internal DirectoryGuard(string exactPath)
        {
            path = exactPath; IntPtr p = Native.CreateFileW(path, 0x00020080, 3, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero);
            Gate.Check(p != IntPtr.Zero && p != new IntPtr(-1), "DIRECTORY_OPEN");
            handle = new Owned(p, 0, delegate(IntPtr v) { Gate.Check(Native.CloseHandle(v), "DIRECTORY_RELEASE"); });
            try { identity = Read(handle.Pointer); }
            catch { handle.Dispose(); throw; }
        }
        private static Dictionary<string, object> Read(IntPtr handle)
        {
            Native.FILE_INFO info; Gate.Check(Native.GetFileInformationByHandle(handle, out info), "DIRECTORY_IDENTITY");
            Gate.Check((info.attributes & 0x410) == 0x10, "DIRECTORY_REPARSE");
            IntPtr owner, group, dacl, sacl, descriptor = IntPtr.Zero;
            try
            {
                Gate.Check(Native.GetSecurityInfo(handle, 1, 5, out owner, out group, out dacl, out sacl, out descriptor) == 0 && descriptor != IntPtr.Zero, "DIRECTORY_SECURITY");
                uint length = Native.GetSecurityDescriptorLength(descriptor); Gate.Check(length >= 20 && length <= 1048576, "DIRECTORY_SECURITY_SIZE");
                byte[] bytes = new byte[length]; Marshal.Copy(descriptor, bytes, 0, (int)length); var security = new RawSecurityDescriptor(bytes, 0);
                Gate.Check(security.Owner != null && security.DiscretionaryAcl != null && (security.ControlFlags & ControlFlags.DiscretionaryAclPresent) != 0, "DIRECTORY_DACL");
                string ownerSid = security.Owner.Value; Gate.Check(TrustedWriter(ownerSid), "DIRECTORY_OWNER");
                foreach (GenericAce ace in security.DiscretionaryAcl)
                {
                    var common = ace as CommonAce; Gate.Check(common != null && !common.IsCallback, "DIRECTORY_ACE");
                    Gate.Check(common.AceQualifier == AceQualifier.AccessAllowed || common.AceQualifier == AceQualifier.AccessDenied, "DIRECTORY_ACE_TYPE");
                    // Include inheritance-only ACEs: these will protect the future
                    // root/records. Never repair an unsafe parent or inherited ACL.
                    const uint writeMask = 0x500D0156;
                    if (common.AceQualifier == AceQualifier.AccessAllowed && (unchecked((uint)common.AccessMask) & writeMask) != 0)
                        Gate.Check(TrustedWriter(common.SecurityIdentifier.Value), "UNTRUSTED_EVIDENCE_WRITER");
                }
                return J.O("volume_serial", (ulong)info.volume, "file_id", (((ulong)info.indexHigh << 32) | info.indexLow).ToString("x16", CultureInfo.InvariantCulture),
                    "owner_sid", ownerSid, "dacl_sddl", security.GetSddlForm(AccessControlSections.Owner | AccessControlSections.Access));
            }
            finally { if (descriptor != IntPtr.Zero) Gate.Check(Native.LocalFree(descriptor) == IntPtr.Zero, "DIRECTORY_SECURITY_RELEASE"); }
        }
        private static bool TrustedWriter(string sid) { return sid == Launcher.CREATOR_SID || sid == Gate.Administrators || sid == "S-1-5-18"; }
        internal Dictionary<string, object> Identity { get { return J.Obj(J.Clone(identity)); } }
        internal void Check()
        {
            Gate.Check(J.Bytes(Read(handle.Pointer)).SequenceEqual(J.Bytes(identity)), "DIRECTORY_IDENTITY_DRIFT");
            using (var reopened = new DirectoryGuard(path)) Gate.Check(J.Bytes(reopened.identity).SequenceEqual(J.Bytes(identity)), "DIRECTORY_PATH_DRIFT");
        }
        public void Dispose() { handle.Dispose(); }
    }

    internal sealed class SourceIdentity
    {
        private const string Worktree = @"F:\AI\worktrees\ai-trading-bot-p3-r1";
        private const string Helper = "scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs";
        private const string Wrapper = "scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1";
        internal readonly string Commit, Tree, HelperHash;
        private readonly string wrapperHash;
        private SourceIdentity(string commit, string tree, string helperHash, string launcherHash)
        { Commit = commit; Tree = tree; HelperHash = helperHash; wrapperHash = launcherHash; }
        private static string Git(string arguments)
        {
            // Read-only, source-owned executable, working directory and arguments.
            // No network, credentials, shell, environment identity, or Git write.
            var start = new System.Diagnostics.ProcessStartInfo(@"C:\Program Files\Git\cmd\git.exe", "--no-replace-objects " + arguments) {
                WorkingDirectory = Worktree, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            foreach (string key in start.EnvironmentVariables.Keys.Cast<string>().Where(k => k.StartsWith("GIT_", StringComparison.OrdinalIgnoreCase)).ToArray())
                start.EnvironmentVariables.Remove(key);
            start.EnvironmentVariables["GIT_CONFIG_NOSYSTEM"] = "1";
            start.EnvironmentVariables["GIT_CONFIG_GLOBAL"] = "NUL";
            using (var process = System.Diagnostics.Process.Start(start))
            {
                Gate.Check(process != null && process.WaitForExit(10000), "SOURCE_GIT_TIMEOUT");
                string result = process.StandardOutput.ReadToEnd();
                Gate.Check(process.ExitCode == 0 && result.Length <= 4096, "SOURCE_GIT"); return result.TrimEnd('\r', '\n');
            }
        }
        private static byte[] Read(string relative) { return File.ReadAllBytes(Path.Combine(Worktree, relative)); }
        private static void Blob(byte[] bytes, string relative)
        {
            byte[] header = Encoding.ASCII.GetBytes("blob " + bytes.Length.ToString(CultureInfo.InvariantCulture) + "\0");
            using (var hash = SHA1.Create())
            {
                hash.TransformBlock(header, 0, header.Length, null, 0); hash.TransformFinalBlock(bytes, 0, bytes.Length);
                J.Eq(Git("rev-parse HEAD:" + relative), BitConverter.ToString(hash.Hash).Replace("-", "").ToLowerInvariant());
            }
        }
        internal static SourceIdentity Capture()
        {
            Gate.Require(); J.Eq(Git("rev-parse --show-toplevel").Replace('/', '\\'), Worktree);
            J.Eq(Git("branch --show-current"), "feature/p3-r1-recovery-implementation");
            string commit = Git("rev-parse HEAD"), tree = Git("show -s --format=%T HEAD"); J.Hex(commit, 40); J.Hex(tree, 40);
            byte[] helper = Read(Helper), wrapper = Read(Wrapper); Blob(helper, Helper); Blob(wrapper, Wrapper);
            string digest = J.Hash(helper);
            var stamps = typeof(Launcher).Assembly.GetCustomAttributes(typeof(System.Reflection.AssemblyMetadataAttribute), false)
                .Cast<System.Reflection.AssemblyMetadataAttribute>().Where(a => a.Key == "P3R1ReviewedHelperSha256").ToArray();
            Gate.Check(stamps.Length == 1 && stamps[0].Value == digest, "LOADED_HELPER_IDENTITY");
            var result = new SourceIdentity(commit, tree, digest, J.Hash(wrapper)); result.Check(); return result;
        }
        internal void Check()
        {
            J.Eq(Git("rev-parse HEAD"), Commit); J.Eq(Git("show -s --format=%T HEAD"), Tree);
            J.Eq(Git("branch --show-current"), "feature/p3-r1-recovery-implementation");
            J.Eq(J.Hash(Read(Helper)), HelperHash); J.Eq(J.Hash(Read(Wrapper)), wrapperHash);
        }
        internal void Validate(List<byte[]> chain)
        {
            if (chain.Count == 0) return;
            var first = J.Obj(J.Parse(chain[0])); var ceremony = J.Obj(first["ceremony"]); var tools = J.Obj(J.Obj(first["facts"])["tools"]);
            J.Eq(ceremony["source_commit"], Commit); J.Eq(ceremony["source_tree"], Tree); J.Eq(tools["helper_sha256"], HelperHash);
        }
    }

    internal sealed class FixedStore : IStore, IRecordFiles, IDisposable
    {
        private DirectoryGuard volume, parent, root;
        internal readonly SourceIdentity Source;
        internal FixedStore()
        {
            Gate.Require(); // No fixed path is opened while disabled.
            Source = SourceIdentity.Capture();
            try
            {
                volume = new DirectoryGuard(@"F:\"); parent = new DirectoryGuard(@"F:\AI");
                uint attr = Native.GetFileAttributesW(Launcher.CEREMONY_EVIDENCE_ROOT); int error = Marshal.GetLastWin32Error();
                if (attr == UInt32.MaxValue) Gate.Check(error == 2, "ROOT_ABSENCE_UNKNOWN");
                else root = new DirectoryGuard(Launcher.CEREMONY_EVIDENCE_ROOT);
            }
            catch { Dispose(); throw; }
        }
        internal bool Absent { get { return root == null; } }
        internal void ProveAbsent()
        {
            Gate.Require(); volume.Check(); parent.Check(); Gate.Check(root == null, "ROOT_EXISTS");
            uint attr = Native.GetFileAttributesW(Launcher.CEREMONY_EVIDENCE_ROOT); int error = Marshal.GetLastWin32Error();
            Gate.Check(attr == UInt32.MaxValue && error == 2, "ROOT_NOT_DEFINITELY_ABSENT");
        }
        internal Dictionary<string, object> CreateRoot()
        {
            Gate.Require(); ProveAbsent();
            Gate.Check(Native.CreateDirectoryW(Launcher.CEREMONY_EVIDENCE_ROOT, IntPtr.Zero), "ROOT_CREATE");
            root = new DirectoryGuard(Launcher.CEREMONY_EVIDENCE_ROOT); Check(); return root.Identity;
        }
        private void Check() { Source.Check(); volume.Check(); parent.Check(); Gate.Check(root != null, "ROOT_MISSING"); root.Check(); }
        public List<byte[]> Load()
        {
            Gate.Require(); if (root == null) { ProveAbsent(); return new List<byte[]>(); }
            Check(); var chain = new RecordArchive(this).Load(); Source.Validate(chain); Check(); return chain;
        }
        public void Publish(byte[] bytes)
        {
            Gate.Require(); Check(); var intended = Load(); intended.Add(bytes); Evidence.Validate(intended); Source.Validate(intended);
            new RecordArchive(this).Publish(bytes); Check();
        }
        string[] IRecordFiles.Names()
        { Gate.Require(); Check(); return Directory.GetFileSystemEntries(Launcher.CEREMONY_EVIDENCE_ROOT).Select(Path.GetFileName).ToArray(); }
        private static string RecordPath(string name)
        {
            Gate.Check(Regex.IsMatch(name, @"\Arecord-[0-9]{3}\.json\z"), "RECORD_NAME");
            return Path.Combine(Launcher.CEREMONY_EVIDENCE_ROOT, name);
        }
        byte[] IRecordFiles.Read(string name)
        {
            Gate.Require(); Check(); string path = RecordPath(name);
            uint attributes = Native.GetFileAttributesW(path); Gate.Check(attributes != UInt32.MaxValue && (attributes & 0x410) == 0, "RECORD_TYPE");
            using (var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                Native.FILE_INFO info; Gate.Check(Native.GetFileInformationByHandle(file.SafeFileHandle.DangerousGetHandle(), out info) && (info.attributes & 0x410) == 0 && info.links == 1, "RECORD_IDENTITY");
                Gate.Check(file.Length > 0 && file.Length <= 4194304, "RECORD_SIZE");
                byte[] bytes = new byte[(int)file.Length]; int read = 0;
                while (read < bytes.Length) { int n = file.Read(bytes, read, bytes.Length - read); Gate.Check(n > 0, "RECORD_SHORT_READ"); read += n; }
                Gate.Check(file.ReadByte() == -1, "RECORD_TRAILING"); Check(); return bytes;
            }
        }
        void IRecordFiles.CreateNew(string name, byte[] bytes)
        {
            Gate.Require(); Check(); string path = RecordPath(name);
            using (var file = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
            { file.Write(bytes, 0, bytes.Length); file.Flush(true); }
            Check();
        }
        public void Dispose()
        {
            try { if (root != null) root.Dispose(); }
            finally { try { if (parent != null) parent.Dispose(); } finally { if (volume != null) volume.Dispose(); } }
        }
    }

    internal static class RealRunner
    {
        private static string PowerShellVersion()
        {
            using (var ps = PowerShell.Create(System.Management.Automation.RunspaceMode.CurrentRunspace))
            {
                ps.AddScript("$PSVersionTable.PSVersion.ToString()", true); var result = ps.Invoke();
                Gate.Check(!ps.HadErrors && result.Count == 1 && result[0].BaseObject is string, "POWERSHELL_VERSION");
                return (string)result[0].BaseObject;
            }
        }
        private static Dictionary<string, object> Host()
        { return J.O("name", Launcher.HOST, "machine_domain_sid", Gate.MachineSid, "os_version", Environment.OSVersion.Version.ToString()); }
        private static SecureString SecureInput()
        {
            Gate.Require(); Gate.Check(Environment.UserInteractive && !Console.IsInputRedirected && !Console.IsOutputRedirected, "LOCAL_CONSOLE_REQUIRED");
            // The source-owned PowerShell launcher defines this function only in
            // its unreachable authorized branch. It returns SecureString directly
            // in this runspace, never through Python, stdout, or another process.
            using (var ps = PowerShell.Create(System.Management.Automation.RunspaceMode.CurrentRunspace))
            {
                ps.AddCommand("Read-P3R1CeremonySecureInput"); var result = ps.Invoke();
                if (ps.HadErrors || result.Count != 1 || !(result[0].BaseObject is SecureString))
                {
                    foreach (PSObject value in result) { var secure = value.BaseObject as SecureString; if (secure != null) secure.Dispose(); }
                    throw new CeremonyException("SECURE_INPUT_INVALID", false);
                }
                return (SecureString)result[0].BaseObject;
            }
        }
        internal static void Run(WindowsAdapter native, FixedStore store)
        {
            Gate.Require(); var current = native.Token(); var journal = new Journal(store, Host());
            if (!store.Absent)
            {
                // Existing attempt markers never authorize dispatch or recovery.
                Gate.Check(Evidence.Next(journal.Confirmed) == "QUALIFICATION_OBSERVED", "RETAINED_STATE_NOT_CONTINUABLE");
                string sid = RetainedSid(journal.Confirmed);
                if (J.S(current["user_sid"]) == sid)
                {
                    var observation = native.Observation(); Proof.Ordinary(current, sid);
                    Console.WriteLine(new UTF8Encoding(false, true).GetString(J.Bytes(observation)));
                    return; // Read-only facts from a manually established desktop.
                }
                Proof.Creator(current);
                try { QualifyTransferredObservation(native, journal, sid); }
                catch
                {
                    if (!journal.Halted) journal.Stop("QUALIFICATION", "GATE_REJECTED", "NONE", null, null);
                    throw new CeremonyException("QUALIFICATION_UNCERTAIN", journal.EffectMayHaveOccurred);
                }
                return;
            }
            Proof.Creator(current); var users = native.UsersIdentity(); var absence = Proof.Absence(native); store.ProveAbsent();
            // Inspect all group/logon prerequisites before root creation or prompt.
            native.Inventory(null);
            var root = store.CreateRoot();
            journal.Advance("PREFLIGHT", J.O("creator_token", current, "absence", absence, "root_absent", true, "root_identity", root,
                "tools", J.O("powershell_version", PowerShellVersion(), "helper_source_commit", store.Source.Commit,
                    "helper_source_tree", store.Source.Tree, "helper_sha256", store.Source.HelperHash,
                    "netapi32_version", System.Diagnostics.FileVersionInfo.GetVersionInfo(Path.Combine(Environment.SystemDirectory, "netapi32.dll")).FileVersion),
                "users_identity", users, "baseline_mode", "CONDITIONAL_USERS"));
            SecureString secret = null;
            string boundary = "SECURE_INPUT";
            try
            {
                secret = SecureInput(); current = native.Token(); Proof.Creator(current); absence = Proof.Absence(native);
                boundary = "CREATE";
                journal.Advance("ACCOUNT_CREATION_ATTEMPTED", J.O("absence", absence, "creator_token", current,
                    "secure_input_method", "READ_HOST_SECURESTRING_GLOBALALLOCUNICODE", "creation_surface", "NETAPI32_NETUSERADD_LEVEL1", "options", Proof.Options()));
                SecureString transferred = secret; secret = null; // Native method owns disposal from here.
                WindowsAdapter.CreateResult create;
                try { create = native.CreateAccount(transferred, journal); } finally { transferred = null; }
                if (create.Status != 0)
                {
                    journal.Stop("CREATE", create.Status == 2224 ? "COLLISION" : "UNCERTAIN", "NetUserAdd", create.Status, create.Parameter); return;
                }
                journal.Advance("ACCOUNT_CREATED", J.O("net_status", 0UL, "creation_return_confirmed", true, "password_buffer_zero_freed", true, "securestring_disposed", true));
                boundary = "READBACK";
                var account = native.Account(); string sid = J.S(account["sid"]); journal.Advance("ACCOUNT_SID_READ_BACK", J.O("account", account));
                boundary = "USERS";
                var direct = native.Groups(0); string branch = Proof.Branch(direct);
                CheckDirectInventory(native.Inventory(sid), direct, sid);
                var freshUsers = native.UsersIdentity(); Gate.Check(J.Bytes(users).SequenceEqual(J.Bytes(freshUsers)), "USERS_DRIFT");
                journal.Advance("USERS_BASELINE_SELECTED", J.O("branch", branch, "direct_view", direct, "users_identity", freshUsers));
                if (branch == "ADD_USERS")
                {
                    current = native.Token(); Proof.Creator(current); J.Eq(native.Account()["sid"], sid);
                    freshUsers = native.UsersIdentity(); Gate.Check(J.Bytes(users).SequenceEqual(J.Bytes(freshUsers)), "USERS_DRIFT");
                    direct = native.Groups(0); Gate.Check(Proof.Groups(direct, 0).Count == 0, "USERS_NOT_EMPTY");
                    journal.Advance("USERS_ASSIGNMENT_ATTEMPTED", J.O("group_sid", Launcher.BUILTIN_USERS_SID, "member_sid", sid,
                        "creator_token", current, "direct_view", direct, "users_identity", freshUsers));
                    uint groupStatus = native.AssignUsers(sid, J.S(freshUsers["resolved_name"]), journal);
                    if (groupStatus != 0) { journal.Stop("USERS", "UNCERTAIN", "NetLocalGroupAddMembers", groupStatus, null); return; }
                    direct = native.Groups(0); J.Eq(Proof.Branch(direct), "ALREADY_USERS"); J.Eq(native.Account()["sid"], sid);
                    Gate.Check(J.Bytes(users).SequenceEqual(J.Bytes(native.UsersIdentity())), "USERS_DRIFT"); CheckDirectInventory(native.Inventory(sid), direct, sid);
                    journal.Advance("USERS_ASSIGNMENT_CONFIRMED", J.O("group_sid", Launcher.BUILTIN_USERS_SID, "member_sid", sid,
                        "net_status", 0UL, "direct_view", direct, "identity_continuity_passed", true));
                }
                // No physical logon preparation or launch occurs here. The next
                // invocation is read-only qualification after separate approval.
            }
            catch (CeremonyException)
            {
                if (!journal.Halted) journal.Stop(boundary, "UNCERTAIN", "NONE", null, null);
                throw;
            }
            catch
            {
                if (!journal.Halted) journal.Stop(boundary, "UNCERTAIN", "NONE", null, null);
                throw new CeremonyException("UNCERTAIN", journal.EffectMayHaveOccurred);
            }
            finally { if (secret != null) { secret.Dispose(); secret = null; } }
        }
        private static void CheckDirectInventory(List<object> edges, object direct, string sid)
        {
            var actual = new HashSet<string>(edges.Where(v => J.S(J.Obj(v)["member_sid"]) == sid).Select(v => J.S(J.Obj(v)["group_sid"])));
            Gate.Check(actual.SetEquals(Proof.Groups(direct, 0)), "DIRECT_INVENTORY");
        }
        private static string RetainedSid(List<byte[]> chain)
        {
            foreach (byte[] bytes in chain)
            { var r = J.Obj(J.Parse(bytes)); if (J.S(r["event"]) == "ACCOUNT_SID_READ_BACK") return J.S(J.Obj(J.Obj(r["facts"])["account"])["sid"]); }
            throw new CeremonyException("RETAINED_SID_MISSING", false);
        }
        private static void QualifyTransferredObservation(WindowsAdapter native, Journal journal, string sid)
        {
            Gate.Require(); Proof.Creator(native.Token());
            // This is the ceremony's explicit operator-observed-console transfer,
            // not caller-created retained-state authority. Closed sanitized facts
            // are independently reconciled in the creator process before retaining.
            Gate.Check(!Console.IsInputRedirected && !Console.IsOutputRedirected, "LOCAL_CONSOLE_REQUIRED");
            Console.WriteLine("Enter the complete canonical sanitized observation from the candidate desktop console (never credentials):");
            string text = Console.ReadLine(); Gate.Check(text != null && text.Length <= 2097152, "OBSERVATION_TRANSFER");
            var observation = J.Obj(J.Parse(new UTF8Encoding(false, true).GetBytes(text))); Qualification.Shape(observation);
            J.Eq(J.Obj(observation["account"])["sid"], sid);
            Gate.Check(J.Bytes(native.Account()).SequenceEqual(J.Bytes(observation["account"])), "ACCOUNT_TRANSFER_DRIFT");
            Gate.Check(J.Bytes(native.Groups(0)).SequenceEqual(J.Bytes(observation["direct_view"])) &&
                J.Bytes(native.Groups(1)).SequenceEqual(J.Bytes(observation["indirect_view"])), "GROUP_TRANSFER_DRIFT");
            Gate.Check(J.Bytes(native.Inventory(sid)).SequenceEqual(J.Bytes(observation["relevant_edges"])), "EDGE_TRANSFER_DRIFT");
            Gate.Check(J.Bytes(native.Rights(sid, J.Arr(observation["effective_groups"]).Select(v => J.S(J.Obj(v)["sid"])))).SequenceEqual(J.Bytes(observation["rights"])), "RIGHTS_TRANSFER_DRIFT");
            Console.WriteLine(new UTF8Encoding(false, true).GetString(J.Bytes(observation)));
            Console.WriteLine("Type EXACT_CONSOLE_MATCH only after comparing the entire displayed observation to the genuine candidate console:");
            Gate.Check(Console.ReadLine() == "EXACT_CONSOLE_MATCH", "OBSERVATION_TRANSFER_UNCONFIRMED");
            journal.Advance("QUALIFICATION_OBSERVED", observation); Qualification.Accept(observation); string hash = J.Hash(journal.Confirmed.Last());
            journal.Advance("GROUPS_QUALIFIED", J.O("observation_sha256", hash, "direct_baseline_passed", true, "indirect_review_passed", true, "special_authority_review_passed", true, "privileges_review_passed", true));
            Proof.Creator(native.Token()); J.Eq(native.Account()["sid"], sid);
            journal.Advance("TOKEN_QUALIFIED", J.O("observation_sha256", hash, "token_gate_passed", true, "enabled_recheck_passed", true, "identity_continuity_passed", true));
        }
    }
}
