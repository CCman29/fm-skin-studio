using System;
using System.Reflection;

namespace FMSkinStudio.GameLink
{
    /// <summary>Asks FM27 to reload its skins, the same as the game's own reload: finds the skin subsystem
    /// and calls its public Reload(). Looked up by reflection so a game update that renames it fails softly.</summary>
    internal static class SkinReload
    {
        public static object Run()
        {
            var lattice = FindType("FM.Lattice", "FM.Lattice.LatticeSubsystem");
            var registry = FindType("SI.Core", "SI.Core.GameSubsystems");
            if (lattice == null || registry == null) return new { error = "This FM27 version's skin reload wasn't found" };
            object instance = null;
            try
            {
                var get = registry.GetMethod("GetOptional", BindingFlags.Public | BindingFlags.Static)
                       ?? registry.GetMethod("Get", BindingFlags.Public | BindingFlags.Static);
                instance = get?.MakeGenericMethod(lattice).Invoke(null, get.GetParameters().Length == 0 ? null : new object[get.GetParameters().Length]);
            }
            catch (Exception e) { Plugin.L.LogWarning($"Subsystem lookup failed: {e.InnerException?.Message ?? e.Message}"); }
            if (instance == null) return new { error = "FM27's skin system isn't ready yet" };
            var reload = lattice.GetMethod("Reload", BindingFlags.Public | BindingFlags.Instance, Type.EmptyTypes);
            if (reload == null) return new { error = "This FM27 version's skin reload wasn't found" };
            reload.Invoke(instance, null);
            return new { reloaded = true };
        }

        private static Type FindType(string assembly, string name)
        {
            foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
                if (a.GetName().Name == assembly) return a.GetType(name);
            return null;
        }
    }
}
