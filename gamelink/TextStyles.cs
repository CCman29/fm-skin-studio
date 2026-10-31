using System;
using System.Collections.Generic;
using Il2CppInterop.Runtime;
using UnityEngine;
using UnityEngine.TextCore.Text;

namespace FMSkinStudio.GameLink
{
    /// <summary>FM27's text style sheets (named rich-text styles such as the one used for club and player names).
    /// Changes are made in memory only and every original is kept, so Restore (or restarting FM27) undoes them.</summary>
    internal static class TextStyles
    {
        private static readonly Dictionary<string, string> s_originals = new Dictionary<string, string>();

        private static IEnumerable<(TextStyleSheet sheet, TextStyle style)> All()
        {
            foreach (var o in Resources.FindObjectsOfTypeAll(Il2CppType.Of<TextStyleSheet>()))
            {
                var sheet = o.TryCast<TextStyleSheet>();
                var list = sheet?.styles;
                if (list == null) continue;
                for (int i = 0; i < list.Count; i++)
                {
                    var style = list[i];
                    if (style != null) yield return (sheet, style);
                }
            }
        }

        public static object List()
        {
            var rows = new List<object>();
            foreach (var (sheet, style) in All())
                rows.Add(new { sheet = sheet.name, name = style.name, open = style.styleOpeningDefinition, close = style.styleClosingDefinition });
            return new { styles = rows };
        }

        public static object Set(string name, string opening)
        {
            int n = Apply(name, opening);
            return n == 0 ? new { error = "No text style called " + name } : (object)new { ok = true, changed = n };
        }

        /// <summary>Sets a style's opening tags; returns how many sheets had it (0 while FM hasn't loaded them yet).</summary>
        public static int Apply(string name, string opening)
        {
            int n = 0;
            foreach (var (sheet, style) in All())
            {
                if (style.name != name) continue;
                var key = sheet.name + "/" + name;
                if (!s_originals.ContainsKey(key)) s_originals[key] = style.styleOpeningDefinition;
                style.m_OpeningDefinition = opening;
                style.RefreshStyle();
                sheet.RefreshStyles();
                n++;
            }
            return n;
        }

        public static object Restore()
        {
            int n = 0;
            foreach (var (sheet, style) in All())
            {
                if (!s_originals.TryGetValue(sheet.name + "/" + style.name, out var original)) continue;
                style.m_OpeningDefinition = original;
                style.RefreshStyle();
                sheet.RefreshStyles();
                n++;
            }
            s_originals.Clear();
            return new { ok = true, restored = n };
        }
    }
}
