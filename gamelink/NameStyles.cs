using System;
using System.Collections.Generic;
using System.Reflection;
using Il2CppInterop.Runtime;
using UnityEngine;

namespace FMSkinStudio.GameLink
{
    /// <summary>The colours FM27 writes into text for clickable names (clubs, teams, competitions, people...), kept in its
    /// EmbeddedDataHandler data asset. Only the white ones are changed, so your club's and other managers' colours stay;
    /// every original is kept for Restore. Changes are in memory only.</summary>
    internal static class NameStyles
    {
        private static readonly Dictionary<string, (object owner, PropertyInfo prop, object original)> s_originals =
            new Dictionary<string, (object, PropertyInfo, object)>();

        private static IEnumerable<object> Handlers()
        {
            Assembly asm;
            try { asm = Assembly.Load("FM.UI"); } catch (Exception) { yield break; }
            var type = asm.GetType("FM.UI.EmbeddedDataHandler");
            if (type == null) yield break;
            foreach (var o in Resources.FindObjectsOfTypeAll(Il2CppType.From(type)))
                yield return Activator.CreateInstance(type, o.Pointer);
        }

        /// <summary>Every colour reachable from the handler's style data: path -> value.</summary>
        private static void Walk(object o, string path, int depth, List<(string path, object owner, PropertyInfo prop, Color colour)> found,
            HashSet<IntPtr> seen)
        {
            if (o == null || depth > 4) return;
            if (o is Il2CppInterop.Runtime.InteropTypes.Il2CppObjectBase b && !seen.Add(b.Pointer)) return;
            foreach (var p in o.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
            {
                if (!p.Name.StartsWith("m_") || p.GetIndexParameters().Length > 0 || !p.CanRead) continue;
                var t = p.PropertyType;
                object v;
                try { v = p.GetValue(o); } catch (Exception) { continue; }
                if (v == null) continue;
                var here = path + "." + p.Name;
                if (t == typeof(Color)) found.Add((here, o, p, (Color)v));
                else if (t == typeof(Color32)) found.Add((here, o, p, (Color)(Color32)v));
                else if (!t.IsValueType && t != typeof(string) && (t.Assembly.GetName().Name.StartsWith("FM.") || t.Assembly.GetName().Name.StartsWith("SI.")))
                    Walk(v, here, depth + 1, found, seen);
            }
        }

        private static List<(string path, object owner, PropertyInfo prop, Color colour)> All()
        {
            var found = new List<(string, object, PropertyInfo, Color)>();
            var seen = new HashSet<IntPtr>();
            foreach (var h in Handlers()) Walk(h, "handler", 0, found, seen);
            return found;
        }

        public static object List()
        {
            var rows = new List<object>();
            foreach (var (path, _, _, c) in All()) rows.Add(new { path, colour = "#" + ColorUtility.ToHtmlStringRGBA(c) });
            return new { colours = rows };
        }

        private static bool IsWhite(Color c) => c.r > 0.93f && c.g > 0.93f && c.b > 0.93f;

        /// <summary>Turns FM's white name colours into the given colour; returns how many changed (0 before FM loads them).</summary>
        public static int Apply(Color colour)
        {
            int n = 0;
            foreach (var (path, owner, prop, c) in All())
            {
                var key = path;
                var original = s_originals.TryGetValue(key, out var o) ? (Color)Unbox(o.original) : c;
                if (!IsWhite(original)) continue;
                if (!s_originals.ContainsKey(key)) s_originals[key] = (owner, prop, prop.GetValue(owner));
                var keepAlpha = new Color(colour.r, colour.g, colour.b, original.a);
                prop.SetValue(owner, prop.PropertyType == typeof(Color32) ? (object)(Color32)keepAlpha : keepAlpha);
                n++;
            }
            return n;
        }

        public static int Restore()
        {
            int n = 0;
            foreach (var (owner, prop, original) in s_originals.Values)
            {
                try { prop.SetValue(owner, original); n++; } catch (Exception) { /* the asset was unloaded */ }
            }
            s_originals.Clear();
            return n;
        }

        private static Color Unbox(object v) => v is Color32 c32 ? (Color)c32 : (Color)v;
    }
}
