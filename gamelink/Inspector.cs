using System;
using System.Collections.Generic;
using System.Reflection;
using Il2CppInterop.Runtime;
using UnityEngine;
using UnityEngine.UIElements;

namespace FMSkinStudio.GameLink
{
    /// <summary>Point-and-inspect for skin authors: while switched on from the studio, Ctrl+F12 records the UI element under
    /// the mouse (and the few elements stacked at that point): type, name, classes and colours. Read-only, and it only
    /// looks near the pointer, never across the whole interface.</summary>
    internal static class Inspector
    {
        private const int MaxResults = 20, MaxWalk = 400, MaxUnder = 30;
        private static bool s_on;
        private static readonly List<object> s_results = new List<object>();
        private static PropertyInfo s_keyboardCurrent, s_mouseCurrent;
        private static bool s_inputLooked;

        private static float s_dueAt = -1f;

        public static object On() { s_on = true; return new { on = true }; }

        /// <summary>Record what's under the pointer after a delay, for things a key press would close (menus).</summary>
        public static object After(float seconds)
        {
            s_dueAt = Time.realtimeSinceStartup + Mathf.Clamp(seconds, 1f, 30f);
            return new { due = seconds };
        }
        public static object Off() { s_on = false; return new { on = false }; }

        public static object Results(bool clear)
        {
            var copy = s_results.ToArray();
            if (clear) s_results.Clear();
            return new { on = s_on, results = copy };
        }

        public static void Tick()
        {
            bool timed = s_dueAt > 0 && Time.realtimeSinceStartup >= s_dueAt;
            if (!s_on && !timed) return;
            try
            {
                if (timed) s_dueAt = -1f;
                else if (!HotkeyPressed()) return;
                var mouse = MousePosition();
                if (mouse == null) { Add(new { error = "Couldn't read the mouse position" }); return; }
                Add(InspectAt(mouse.Value));
            }
            catch (Exception e) { Add(new { error = e.Message }); }
        }

        private static void Add(object result)
        {
            if (s_results.Count >= MaxResults) s_results.RemoveAt(0);
            s_results.Add(result);
            Plugin.L.LogInfo("Inspect recorded");
        }

        // ---- input (FM27 uses Unity's Input System; looked up by reflection so nothing else depends on it) ----------
        private static void FindInput()
        {
            if (s_inputLooked) return;
            s_inputLooked = true;
            Assembly asm = null;
            try { asm = Assembly.Load("Unity.InputSystem"); } catch (Exception) { /* not available */ }
            s_keyboardCurrent = asm?.GetType("UnityEngine.InputSystem.Keyboard")?.GetProperty("current", BindingFlags.Public | BindingFlags.Static);
            s_mouseCurrent = asm?.GetType("UnityEngine.InputSystem.Mouse")?.GetProperty("current", BindingFlags.Public | BindingFlags.Static);
        }

        private static object Prop(object o, string name) => o?.GetType().GetProperty(name)?.GetValue(o);

        private static bool HotkeyPressed()
        {
            FindInput();
            var kb = s_keyboardCurrent?.GetValue(null);
            if (kb == null) return false;
            var pressed = Prop(Prop(kb, "f12Key"), "wasPressedThisFrame") as bool? ?? false;
            if (!pressed) return false;
            return Prop(Prop(kb, "ctrlKey"), "isPressed") as bool? ?? false;
        }

        private static Vector2? MousePosition()
        {
            FindInput();
            var position = Prop(s_mouseCurrent?.GetValue(null), "position");
            var read = position?.GetType().GetMethod("ReadValue", Type.EmptyTypes);
            return read?.Invoke(position, null) is Vector2 v ? v : (Vector2?)null;
        }

        // ---- picking ------------------------------------------------------------------------------------------------
        private static object InspectAt(Vector2 screen)
        {
            var docs = new List<UIDocument>();
            foreach (var o in Resources.FindObjectsOfTypeAll(Il2CppType.Of<UIDocument>()))
            {
                var d = o.TryCast<UIDocument>();
                if (d != null && d.isActiveAndEnabled && d.rootVisualElement?.panel != null) docs.Add(d);
            }
            docs.Sort((a, b) => b.sortingOrder.CompareTo(a.sortingOrder));
            var flipped = new Vector2(screen.x, Screen.height - screen.y);  // panels measure from the top-left
            foreach (var doc in docs)
            {
                var panel = doc.rootVisualElement.panel;
                var point = RuntimePanelUtils.ScreenToPanel(panel, flipped);
                var picked = panel.Pick(point);
                if (picked == null) continue;
                var chain = new List<object>();
                VisualElement top = picked;
                for (int i = 0; i < 8 && top != null; i++, top = top.hierarchy.parent) chain.Add(Describe(top));
                // everything visible at the point inside a small area around the picked element (icons are often not pickable)
                var area = picked;
                for (int i = 0; i < 3 && area.hierarchy.parent != null; i++) area = area.hierarchy.parent;
                var under = new List<object>();
                int budget = MaxWalk;
                Walk(area, point, under, ref budget, 0);
                return new { at = new[] { (int)point.x, (int)point.y }, document = doc.gameObject.name, picked = chain, under };
            }
            return new { at = new[] { (int)flipped.x, (int)flipped.y }, error = "Nothing under the pointer" };
        }

        private static void Walk(VisualElement ve, Vector2 point, List<object> found, ref int budget, int depth)
        {
            if (ve == null || budget-- <= 0 || depth > 14 || found.Count >= MaxUnder) return;
            if (ve.resolvedStyle.display == DisplayStyle.None || ve.resolvedStyle.visibility == Visibility.Hidden) return;
            if (!ve.worldBound.Contains(point)) return;
            found.Add(Describe(ve));
            int n = ve.hierarchy.childCount;
            for (int i = 0; i < n && budget > 0; i++) Walk(ve.hierarchy[i], point, found, ref budget, depth + 1);
        }

        private static object Describe(VisualElement ve)
        {
            var classes = new List<string>();
            try
            {
                var list = new Il2CppSystem.Collections.Generic.List<string>(ve.GetClasses());
                for (int i = 0; i < list.Count; i++) classes.Add(list[i]);
            }
            catch (Exception) { /* classes are optional */ }
            string text = null;
            var te = ve.TryCast<TextElement>();
            if (te != null && !string.IsNullOrEmpty(te.text)) text = te.text.Length > 80 ? te.text.Substring(0, 80) : te.text;
            var s = ve.resolvedStyle;
            var r = ve.worldBound;
            return new
            {
                type = ve.GetIl2CppType().Name,
                name = string.IsNullOrEmpty(ve.name) ? null : ve.name,
                classes,
                text,
                color = Hex(s.color),
                tint = Hex(s.unityBackgroundImageTintColor),
                background = Hex(s.backgroundColor),
                hasImage = s.backgroundImage.texture != null || s.backgroundImage.sprite != null || s.backgroundImage.vectorImage != null,
                rect = new[] { (int)r.x, (int)r.y, (int)r.width, (int)r.height },
            };
        }

        private static string Hex(Color c) => $"#{(int)(c.r * 255):x2}{(int)(c.g * 255):x2}{(int)(c.b * 255):x2}{(int)(c.a * 255):x2}";
    }
}
