# MST-GCN 모델 아키텍처

class cheb_conv(nn.Module):
    '''
    K-order chebyshev graph convolution
    '''
    def __init__(self, K, cheb_polynomials, in_channels, out_channels):
        super(cheb_conv, self).__init__()
        self.K = K
        self.cheb_polynomials = cheb_polynomials
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.DEVICE = cheb_polynomials[0].device

        self.Theta = nn.ParameterList([
            nn.Parameter(torch.FloatTensor(in_channels, out_channels).to(self.DEVICE))
            for _ in range(K)
        ])

    def forward(self, x):
        batch_size, num_of_vertices, in_channels, num_of_timesteps = x.shape

        outputs = []
        for time_step in range(num_of_timesteps):
            graph_signal = x[:, :, :, time_step]
            output = torch.zeros(batch_size, num_of_vertices, self.out_channels).to(self.DEVICE)

            for k in range(self.K):
                T_k = self.cheb_polynomials[k]
                theta_k = self.Theta[k]
                rhs = torch.matmul(T_k, graph_signal)
                output = output + torch.matmul(rhs, theta_k)

            outputs.append(output.unsqueeze(-1))

        return F.relu(torch.cat(outputs, dim=-1))


class MSTGCN_block(nn.Module):
    def __init__(self, DEVICE, in_channels, K, nb_chev_filter, nb_time_filter,
                 time_conv_strides, cheb_polynomials, num_of_vertices, num_of_timesteps):
        super(MSTGCN_block, self).__init__()

        self.cheb_conv = cheb_conv(K, cheb_polynomials, in_channels, nb_chev_filter)
        self.time_conv = nn.Conv2d(nb_chev_filter, nb_time_filter,
                                   kernel_size=(1, 3), stride=(1, time_conv_strides),
                                   padding=(0, 1))
        self.residual_conv = nn.Conv2d(in_channels, nb_time_filter,
                                       kernel_size=(1, 1), stride=(1, time_conv_strides))
        self.ln = nn.LayerNorm(nb_time_filter)

    def forward(self, x):
        spatial_gcn = self.cheb_conv(x)
        time_conv_output = self.time_conv(spatial_gcn.permute(0, 2, 1, 3))
        time_conv_output = time_conv_output.permute(0, 2, 1, 3)

        x_residual = self.residual_conv(x.permute(0, 2, 1, 3))
        x_residual = x_residual.permute(0, 2, 1, 3)

        out = F.relu(x_residual + time_conv_output)
        out = out.permute(0, 1, 3, 2)
        out = self.ln(out)
        out = out.permute(0, 1, 3, 2)

        return out


class MSTGCN_submodule(nn.Module):
    def __init__(self, DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter,
                 time_strides, cheb_polynomials, num_for_predict, len_input, num_of_vertices):
        super(MSTGCN_submodule, self).__init__()

        self.BlockList = nn.ModuleList()

        self.BlockList.append(
            MSTGCN_block(DEVICE, in_channels, K, nb_chev_filter, nb_time_filter,
                         time_strides, cheb_polynomials, num_of_vertices, len_input)
        )

        for _ in range(nb_block - 1):
            self.BlockList.append(
                MSTGCN_block(DEVICE, nb_time_filter, K, nb_chev_filter, nb_time_filter,
                             1, cheb_polynomials, num_of_vertices, len_input // time_strides)
            )

        self.final_conv = nn.Conv2d(int(len_input / time_strides), num_for_predict,
                                   kernel_size=(1, nb_time_filter))
        self.W = nn.Parameter(torch.FloatTensor(num_of_vertices, num_for_predict))

        self.DEVICE = DEVICE
        self.to(DEVICE)

    def forward(self, x):
        for block in self.BlockList:
            x = block(x)

        output = self.final_conv(x.permute(0, 3, 1, 2))
        output = output[:, :, :, 0].permute(0, 2, 1)
        output = output * self.W

        return output


class MSTGCN(nn.Module):
    '''
    Multi-Scale Temporal Graph Convolutional Networks
    '''
    def __init__(self, DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter,
                 time_strides, cheb_polynomials, num_for_predict, num_of_vertices,
                 len_hour, len_day, len_week):
        super(MSTGCN, self).__init__()

        self.num_for_predict = num_for_predict

        self.hour_module = MSTGCN_submodule(
            DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter,
            time_strides, cheb_polynomials, num_for_predict, len_hour, num_of_vertices
        )

        self.day_module = MSTGCN_submodule(
            DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter,
            time_strides, cheb_polynomials, num_for_predict, len_day, num_of_vertices
        )

        self.week_module = MSTGCN_submodule(
            DEVICE, nb_block, in_channels, K, nb_chev_filter, nb_time_filter,
            time_strides, cheb_polynomials, num_for_predict, len_week, num_of_vertices
        )

    def forward(self, x_hour, x_day, x_week):
        hour_output = self.hour_module(x_hour)
        day_output = self.day_module(x_day)
        week_output = self.week_module(x_week)

        output = hour_output + day_output + week_output

        return output