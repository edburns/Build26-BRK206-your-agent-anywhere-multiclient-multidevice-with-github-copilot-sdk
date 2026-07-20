param(
    [int]$N = 10,
    [ValidateSet('fibonacci','factorial')][string]$Operation = 'fibonacci'
)

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

function Get-Factorial {
    [CmdletBinding()]
    param(
        [int]$N
    )

    if ($N -lt 0) {
        throw "N must be a non-negative integer. Got: $N"
    }

    $result = [bigint]1
    for ($i = 2; $i -le $N; $i++) {
        $result = $result * [bigint]$i
    }

    return $result
}

if ($MyInvocation.InvocationName -ne '.') {
    switch ($Operation) {
        'fibonacci' {
            $result = Get-Fibonacci -N $N
            Write-Output "Fibonacci($N) = $result"
        }
        'factorial' {
            $result = Get-Factorial -N $N
            Write-Output "Factorial($N) = $result"
        }
        default {
            throw "Unsupported operation: $Operation"
        }
    }
}
