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
}
