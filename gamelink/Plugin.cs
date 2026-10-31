// FM Skin Studio Game Link: a small helper that runs inside Football Manager 27 (BepInEx 6, IL2CPP).
// It reloads skins, takes screenshots and applies a skin's system text colour; it never changes saves or game logic. It answers the studio over 127.0.0.1 only, with a token written to
// BepInEx/config, and runs every request on the game's main thread.
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using BepInEx;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;
using Il2CppInterop.Runtime;
using Il2CppInterop.Runtime.Injection;
using UnityEngine;
using UnityEngine.UIElements;

namespace FMSkinStudio.GameLink
{
    [BepInPlugin("com.matergames.fmskinstudio.gamelink", "FM Skin Studio Game Link", "1.2.0")]
    public class Plugin : BasePlugin
    {
        internal static ManualLogSource L;

        public override void Load()
        {
            L = Log;
            ClassInjector.RegisterTypeInIl2Cpp<Pump>();
            AddComponent<Pump>();
            Server.Start(Path.Combine(Paths.ConfigPath, "FMSkinStudio.GameLink.token"));
            L.LogInfo("FM Skin Studio Game Link ready on 127.0.0.1:" + Server.Port);
        }
    }

    /// <summary>Runs queued requests on Unity's main thread.</summary>
    public class Pump : MonoBehaviour
    {
        public Pump(IntPtr ptr) : base(ptr) { }
        private void Update() { Server.RunQueued(); SkinFollower.Tick(Time.realtimeSinceStartup); Inspector.Tick(); }
    }

    internal static class Server
    {
        public const int Port = 47827;
        private static string _token;
        private static readonly ConcurrentQueue<(Dictionary<string, JsonElement> req, TaskCompletionSource<object> done)> Queue = new();

        public static void Start(string tokenFile)
        {
            _token = Guid.NewGuid().ToString("N");
            Directory.CreateDirectory(Path.GetDirectoryName(tokenFile));
            File.WriteAllText(tokenFile, _token);
            var t = new Thread(Listen) { IsBackground = true, Name = "FMSkinStudio.GameLink" };
            t.Start();
        }

        private static void Listen()
        {
            var listener = new TcpListener(IPAddress.Loopback, Port);
            try { listener.Start(); }
            catch (Exception e) { Plugin.L.LogError("Game Link couldn't listen: " + e.Message); return; }
            while (true)
            {
                var client = listener.AcceptTcpClient();
                ThreadPool.QueueUserWorkItem(_ => Handle(client));
            }
        }

        private static void Handle(TcpClient client)
        {
            using (client)
            using (var stream = client.GetStream())
            using (var reader = new StreamReader(stream, Encoding.UTF8))
            {
                object reply;
                try
                {
                    var req = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(reader.ReadLine() ?? "{}");
                    if (!req.TryGetValue("token", out var tok) || tok.GetString() != _token) reply = new { error = "Not authorised" };
                    else
                    {
                        var done = new TaskCompletionSource<object>();
                        Queue.Enqueue((req, done));
                        reply = done.Task.Wait(TimeSpan.FromSeconds(20)) ? done.Task.Result : new { error = "The game didn't answer in time" };
                    }
                }
                catch (Exception e) { reply = new { error = e.Message }; }
                var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(reply) + "\n");
                stream.Write(bytes, 0, bytes.Length);
            }
        }

        public static void RunQueued()
        {
            while (Queue.TryDequeue(out var job))
            {
                try { job.done.SetResult(Commands.Run(job.req)); }
                catch (Exception e) { job.done.SetResult(new { error = e.GetType().Name + ": " + e.Message }); }
            }
        }
    }

    internal static class Commands
    {
        public static object Run(Dictionary<string, JsonElement> req)
        {
            var command = req.TryGetValue("command", out var c) ? c.GetString() : "";
            switch (command)
            {
                case "ping":
                    return new { ok = true, plugin = "1.2.0", game = Application.version, unity = Application.unityVersion,
                        width = Screen.width, height = Screen.height, skin = SkinFollower.ActiveSkin, nameColour = SkinFollower.NameColour };
                case "screen":  // disabled: walking the UI while FM rebuilds it (e.g. loading a save) can close the game
                    return new { error = "Screen reading is turned off in this version" };
                case "screenshot":
                    var file = req.TryGetValue("path", out var p) ? p.GetString() : null;
                    if (string.IsNullOrEmpty(file)) return new { error = "No path" };
                    ScreenCapture.CaptureScreenshot(file);  // written at the end of this frame
                    return new { ok = true, path = file };
                case "inspectOn":
                    return Inspector.On();
                case "inspectOff":
                    return Inspector.Off();
                case "inspectAfter":
                    return Inspector.After(req.TryGetValue("seconds", out var sec) ? (float)sec.GetDouble() : 6f);
                case "inspectResults":
                    return Inspector.Results(req.TryGetValue("clear", out var cl) && cl.ValueKind == JsonValueKind.True);
                case "nameStyles":
                    return NameStyles.List();
                case "setNameStyles":
                {
                    var hex = req.TryGetValue("colour", out var hc) ? hc.GetString() : null;
                    if (hex == null || !ColorUtility.TryParseHtmlString(hex, out var col)) return new { error = "Give a colour like #0b1f4b" };
                    return new { changed = NameStyles.Apply(col) };
                }
                case "restoreNameStyles":
                    return new { restored = NameStyles.Restore() };
                case "textStyles":
                    return TextStyles.List();
                case "setTextStyle":
                    return TextStyles.Set(req.TryGetValue("name", out var sn) ? sn.GetString() : "",
                        req.TryGetValue("opening", out var so) ? so.GetString() : "");
                case "restoreTextStyles":
                    return TextStyles.Restore();
                case "reloadSkin":
                    SkinFollower.Recheck();
                    return SkinReload.Run();
                default:
                    return new { error = "Unknown command " + command };
            }
        }
    }
}
