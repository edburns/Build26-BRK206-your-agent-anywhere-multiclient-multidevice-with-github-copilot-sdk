function Get-Fibonacci {
    [CmdletBinding()]
    param(
        [int]$N
    )

    if ($N -lt 0) {
        throw "N must be a non-negative integer. Got: $N"
    }

    if ($N -eq 0) {
        return 0
    }

    if ($N -eq 1) {
        return 1
    }

    $previous = 0
    $current = 1

    for ($i = 2; $i -le $N; $i++) {
        $next = $previous + $current
        $previous = $current
        $current = $next
    }

    return $current
}

if ($MyInvocation.InvocationName -ne '.') {
    $result = Get-Fibonacci -N 10
    Write-Output "Fibonacci(10) = $result"
}
