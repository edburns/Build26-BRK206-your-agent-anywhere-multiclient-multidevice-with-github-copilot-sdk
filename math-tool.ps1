function Get-Fibonacci {
    [CmdletBinding()]
    param(
        [int]$N
    )

    if ($N -le 0) { return 0 }
    if ($N -eq 1) { return 1 }

    $prev = 0
    $curr = 1
    for ($i = 2; $i -le $N; $i++) {
        $next = $prev + $curr
        $prev = $curr
        $curr = $next
    }
    return $curr
}

if ($MyInvocation.InvocationName -ne '.') {
    $result = Get-Fibonacci -N 10
    Write-Output "Fibonacci(10) = $result"
}
