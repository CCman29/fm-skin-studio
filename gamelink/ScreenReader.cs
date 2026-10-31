using System;
using System.Collections.Generic;
using Il2CppInterop.Runtime;
using UnityEngine;
using UnityEngine.UIElements;

namespace FMSkinStudio.GameLink
{
    /// <summary>A compact snapshot of the visible UI Toolkit tree: element type, name, classes, position and short text.
    /// Read-only: nothing on screen is changed.</summary>
    internal static class ScreenReader
    {
        public static List<object> Read(int maxNodes)
        {
            var roots = new List<object>();
            int budget = maxNodes;
            foreach (var o in Resources.FindObjectsOfTypeAll(Il2CppType.Of<UIDocument>()))
            {
                var doc = o.TryCast<UIDocument>();
                if (doc == null || !doc.isActiveAndEnabled) continue;
                var root = doc.rootVisualElement;
                if (root == null) continue;
                roots.Add(new { document = doc.gameObject.name, sort = doc.sortingOrder, tree = Walk(root, 0, ref budget) });
            }
            return roots;
        }

        private static object Walk(VisualElement ve, int depth, ref int budget)
        {
            if (ve == null || budget <= 0 || depth > 80) return null;
            if (ve.resolvedStyle.display == DisplayStyle.None || ve.resolvedStyle.visibility == Visibility.Hidden) return null;
            budget--;
            var kids = new List<object>();
            int n = ve.hierarchy.childCount;
            for (int i = 0; i < n && budget > 0; i++)
            {
                var child = Walk(ve.hierarchy[i], depth + 1, ref budget);
                if (child != null) kids.Add(child);
            }
            var r = ve.worldBound;
            string text = null;
            var te = ve.TryCast<TextElement>();
            if (te != null && !string.IsNullOrEmpty(te.text)) text = te.text.Length > 60 ? te.text.Substring(0, 60) : te.text;
            return new
            {
                t = ve.GetIl2CppType().Name,
                n = string.IsNullOrEmpty(ve.name) ? null : ve.name,
                c = Classes(ve),
                r = new[] { (int)r.x, (int)r.y, (int)r.width, (int)r.height },
                txt = text,
                ch = kids.Count > 0 ? kids : null,
            };
        }

        private static List<string> Classes(VisualElement ve)
        {
            var list = new List<string>();
            try
            {
                var e = ve.GetClasses().GetEnumerator();
                var plain = e.Cast<Il2CppSystem.Collections.IEnumerator>();
                while (plain.MoveNext()) list.Add(e.Current);
            }
            catch (Exception) { /* classes are optional in the snapshot */ }
            return list.Count > 0 ? list : null;
        }
    }
}
