<#
.SYNOPSIS
    Computes mathematical sequences: Fibonacci numbers and factorials.

.DESCRIPTION
    Computes Fibonacci numbers or factorials for a given non-negative integer N.
    N must be between 0 and 100 inclusive.

.PARAMETER N
    The input integer. Must be in the range 0-100.

.PARAMETER Operation
    The operation to perform. Valid values: 'fibonacci' (default), 'factorial'.

.EXAMPLE
    .\math-tool.ps1 -N 10
    Fibonacci(10) = 55

.EXAMPLE
    .\math-tool.ps1 -N 5 -Operation factorial
    Factorial(5) = 120

.EXAMPLE
    .\math-tool.ps1 -N 5 -Verbose
    VERBOSE: Computing fibonacci(5) iteratively...
    Fibonacci(5) = 5
#>
[CmdletBinding()]
param(
    [ValidateRange(0, 100)]
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
        return [bigint]0
    }

    if ($N -eq 1) {
        return [bigint]1
    }

    $previous = [bigint]0
    $current = [bigint]1

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
            Write-Verbose "Computing fibonacci($N) iteratively..."
            $result = Get-Fibonacci -N $N
            Write-Output "Fibonacci($N) = $result"
        }
        'factorial' {
            Write-Verbose "Computing factorial($N) iteratively..."
            $result = Get-Factorial -N $N
            Write-Output "Factorial($N) = $result"
        }
        default {
            throw "Unsupported operation: $Operation"
        }
    }
}
