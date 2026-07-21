BeforeAll {
    . "$PSScriptRoot/math-tool.ps1"
}

Describe "Get-Fibonacci" {
    It "returns 0 for N=0" {
        Get-Fibonacci -N 0 | Should -Be 0
    }

    It "returns 1 for N=1" {
        Get-Fibonacci -N 1 | Should -Be 1
    }

    It "returns 55 for N=10" {
        Get-Fibonacci -N 10 | Should -Be 55
    }

    It "returns 6765 for N=20" {
        Get-Fibonacci -N 20 | Should -Be 6765
    }
}

Describe "Get-Factorial" {
    It "throws for negative inputs" {
        { Get-Factorial -N -1 } | Should -Throw "Factorial is undefined for negative integers: -1"
    }

    It "returns 1 for N=0" {
        Get-Factorial -N 0 | Should -Be ([bigint]1)
    }

    It "returns 1 for N=1" {
        Get-Factorial -N 1 | Should -Be ([bigint]1)
    }

    It "returns 120 for N=5" {
        Get-Factorial -N 5 | Should -Be ([bigint]120)
    }

    It "returns 2432902008176640000 for N=20" {
        Get-Factorial -N 20 | Should -Be ([bigint]2432902008176640000)
    }
}

Describe "math-tool.ps1 script output" {
    It "prints Fibonacci(10) = 55 with no arguments" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1"
        ($output -join [Environment]::NewLine) | Should -Match "Fibonacci\(10\) = 55"
    }

    It "prints Fibonacci(15) = 610 with -N 15" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1" -N 15
        ($output -join [Environment]::NewLine) | Should -Match "Fibonacci\(15\) = 610"
    }

    It "prints Fibonacci(0) = 0 with -N 0" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1" -N 0
        ($output -join [Environment]::NewLine) | Should -Match "Fibonacci\(0\) = 0"
    }

    It "prints Factorial(5) = 120 with -Operation factorial -N 5" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1" -Operation factorial -N 5
        ($output -join [Environment]::NewLine) | Should -Match "Factorial\(5\) = 120"
    }

    It "prints Fibonacci(10) = 55 with -Operation fibonacci -N 10" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1" -Operation fibonacci -N 10
        ($output -join [Environment]::NewLine) | Should -Match "Fibonacci\(10\) = 55"
    }

    It "fails validation for -N -1" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1" -N -1 2>&1
        $LASTEXITCODE | Should -Not -Be 0
        ($output -join [Environment]::NewLine) | Should -Match "Cannot validate argument on parameter 'N'"
    }

    It "fails validation for -N 101" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1" -N 101 2>&1
        $LASTEXITCODE | Should -Not -Be 0
        ($output -join [Environment]::NewLine) | Should -Match "Cannot validate argument on parameter 'N'"
    }

    It "includes verbose output with -Verbose -N 5" {
        $output = pwsh -NoProfile -NonInteractive -File "$PSScriptRoot/math-tool.ps1" -Verbose -N 5 4>&1
        ($output -join [Environment]::NewLine) | Should -Match "Computing"
        ($output -join [Environment]::NewLine) | Should -Match "Fibonacci\(5\) = 5"
    }

    It "shows comment-based help with SYNOPSIS" {
        $helpText = Get-Help "$PSScriptRoot/math-tool.ps1" | Out-String -Width 200
        $helpText | Should -Match "SYNOPSIS"
    }
}
