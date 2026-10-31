using System;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace FMSkinStudio.GameLink
{
    /// <summary>Applies the selected skin's system text colour (names of clubs, teams and players), saved by FM Skin Studio
    /// in the skin's fmskinstudio.json. A skin without one, or switching skins, puts FM's own colours back.</summary>
    internal static class SkinFollower
    {
        private static float s_next;
        private static string s_skinKey;  // the skin the colour was last worked out for
        private static bool s_recheck;

        public static string ActiveSkin { get; private set; }
        public static string NameColour { get; private set; }

        /// <summary>Read the skin's setting again (the studio saved it and reloaded the skin).</summary>
        public static void Recheck() => s_recheck = true;

        public static void Tick(float now)
        {
            if (now < s_next) return;
            s_next = now + 5f;  // only asks FM which skin is selected; files are read when that changes
            try
            {
                var (id, display) = AppliedSkin();
                var key = $"{id}|{display}";
                if (key == s_skinKey && !s_recheck) return;
                s_recheck = false;
                s_skinKey = key;
                ActiveSkin = display ?? id;
                var folder = FindFolder(id, display);
                var marker = folder == null ? null : Path.Combine(folder, "fmskinstudio.json");
                var colour = marker != null && File.Exists(marker) ? ReadColour(marker) : null;
                if (colour != null)
                {
                    if (TextStyles.Apply("Norml", $"<color={colour}>") == 0) { s_skinKey = null; return; }  // styles not loaded yet: retry
                    NameColour = colour;  // names drawn from now on use it; ones already on screen update when redrawn
                }
                else if (NameColour != null) { TextStyles.Restore(); NameColour = null; }
                Plugin.L.LogInfo($"Skin '{ActiveSkin}': name colour {(colour ?? "game default")}");
            }
            catch (Exception e) { Plugin.L.LogWarning("Skin check failed: " + e.Message); s_next = now + 30f; }
        }

        private static (string id, string display) AppliedSkin()
        {
            Type Find(string asm, string name)
            {
                foreach (var a in AppDomain.CurrentDomain.GetAssemblies()) if (a.GetName().Name == asm) return a.GetType(name);
                return null;
            }
            var lattice = Find("FM.Lattice", "FM.Lattice.LatticeSubsystem");
            var registry = Find("SI.Core", "SI.Core.GameSubsystems");
            var get = registry?.GetMethod("GetOptional", BindingFlags.Public | BindingFlags.Static);
            if (lattice == null || get == null) return (null, null);
            var sub = get.MakeGenericMethod(lattice).Invoke(null, get.GetParameters().Length == 0 ? null : new object[get.GetParameters().Length]);
            var skin = sub == null ? null : lattice.GetProperty("AppliedSkin")?.GetValue(sub);
            if (skin == null) return (null, null);
            var t = skin.GetType();
            return (t.GetProperty("Id")?.GetValue(skin)?.ToString(), t.GetProperty("DisplayName")?.GetValue(skin)?.ToString());
        }

        private static string FindFolder(string id, string display)
        {
            if (id == null && display == null) return null;
            var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Sports Interactive", "Football Manager 27", "skins");
            if (!Directory.Exists(root)) return null;
            foreach (var dir in Directory.GetDirectories(root))
            {
                if (id != null && (string.Equals(Path.GetFileName(dir), id, StringComparison.OrdinalIgnoreCase) || dir.EndsWith(id, StringComparison.OrdinalIgnoreCase))) return dir;
                var skinJson = Path.Combine(dir, "skin.json");
                if (display == null || !File.Exists(skinJson)) continue;
                try
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(skinJson));
                    if (doc.RootElement.TryGetProperty("Name", out var n) && n.GetString() == display) return dir;
                }
                catch (Exception) { /* not a readable skin */ }
            }
            return null;
        }

        private static string ReadColour(string marker)
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(marker));
                if (doc.RootElement.TryGetProperty("systemText", out var st) && st.TryGetProperty("names", out var n))
                {
                    var c = n.GetString();
                    if (c != null && Regex.IsMatch(c, "^#[0-9a-fA-F]{6,8}$")) return c;
                }
            }
            catch (Exception) { /* unreadable: treat as no colour */ }
            return null;
        }
    }
}
