param(
    [ValidateSet('fibonacci', 'factorial')]
    [string]$Operation = 'fibonacci',
    [int]$N = 10
)

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

function Get-Factorial {
    [CmdletBinding()]
    param(
        [int]$N
    )

    if ($N -le 1) { return ([bigint]1) }

    [bigint]$result = 1
    for ($i = 2; $i -le $N; $i++) {
        $result *= $i
    }

    return $result
}

if ($MyInvocation.InvocationName -ne '.') {
    switch ($Operation) {
        'factorial' {
            $result = Get-Factorial -N $N
            Write-Output "Factorial($N) = $result"
        }
        default {
            $result = Get-Fibonacci -N $N
            Write-Output "Fibonacci($N) = $result"
        }
    }
}
