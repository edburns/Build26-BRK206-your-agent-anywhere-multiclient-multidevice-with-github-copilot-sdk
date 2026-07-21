<#
.SYNOPSIS
Computes Fibonacci or factorial values from the command line.

.DESCRIPTION
Runs an iterative Fibonacci or factorial calculation and prints the result.

.PARAMETER Operation
Selects which operation to run. Supported values are fibonacci and factorial.

.PARAMETER N
Specifies the non-negative integer input for the selected operation.

.EXAMPLE
pwsh -File ./math-tool.ps1 -N 5

.EXAMPLE
pwsh -File ./math-tool.ps1 -Operation factorial -N 5 -Verbose
#>
[CmdletBinding()]
param(
    [ValidateSet('fibonacci', 'factorial')]
    [string]$Operation = 'fibonacci',
    [ValidateRange(0, 100)]
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

    if ($N -lt 0) {
        throw "Factorial is undefined for negative integers: $N"
    }

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
            Write-Verbose "Computing factorial($N) iteratively..."
            $result = Get-Factorial -N $N
            Write-Output "Factorial($N) = $result"
        }
        default {
            Write-Verbose "Computing fibonacci($N) iteratively..."
            $result = Get-Fibonacci -N $N
            Write-Output "Fibonacci($N) = $result"
        }
    }
}
