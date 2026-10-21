param(
  [int]$Seconds = 60,
  [int]$Threads = 20
)

$src = @'
using System;
using System.Diagnostics;
using System.Threading;

public static class LoadGen {
    public static void Burn(int threads, int seconds) {
        long stopAt = Stopwatch.GetTimestamp() + (long)seconds * Stopwatch.Frequency;
        Thread[] ts = new Thread[threads];
        for (int i = 0; i < threads; i++) {
            int seed = i;
            ts[i] = new Thread(() => {
                double x = 1.0 + seed * 0.001, y = 0.5;
                while (Stopwatch.GetTimestamp() < stopAt) {
                    for (int k = 0; k < 5000; k++) {
                        x = x * 1.0000001 + 1.234567;
                        y = y * 0.9999999 - 0.7654321;
                        if (x > 1e9) x -= 1e9;
                        if (y < -1e9) y += 1e9;
                    }
                    if (x == 0.0 && y == 0.0) Console.WriteLine(seed);
                }
            });
            ts[i].IsBackground = true;
            ts[i].Start();
        }
        foreach (Thread t in ts) t.Join();
    }
}
'@
if (-not ('LoadGen' -as [type])) {
  $cp = New-Object System.CodeDom.Compiler.CompilerParameters
  $cp.CompilerOptions = '/optimize+'; $cp.GenerateInMemory = $true
  $cp.ReferencedAssemblies.Add('System.dll') | Out-Null
  Add-Type -TypeDefinition $src -CompilerParameters $cp
}

$sw = [Diagnostics.Stopwatch]::StartNew()
[LoadGen]::Burn($Threads, $Seconds)
"burned {0} threads for {1:N1}s" -f $Threads, $sw.Elapsed.TotalSeconds
