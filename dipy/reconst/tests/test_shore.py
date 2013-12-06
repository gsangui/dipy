import numpy as np
from dipy.data import get_data, two_shells_voxels, three_shells_voxels, get_sphere
from dipy.data.fetcher import (fetch_isbi2013_2shell, read_isbi2013_2shell,
                               fetch_sherbrooke_3shell, read_sherbrooke_3shell)
from dipy.reconst.shore import ShoreModel
from dipy.reconst.shm import QballModel
from dipy.reconst.peaks import gfa, peak_directions
from dipy.core.gradients import gradient_table
from numpy.testing import (assert_equal,
                           assert_almost_equal,
                           run_module_suite,
                           assert_array_equal,
                           assert_raises)
from dipy.sims.voxel import (SticksAndBall, multi_tensor, all_tensor_evecs,
                             multi_tensor_odf)
from dipy.core.subdivide_octahedron import create_unit_sphere
from dipy.core.sphere_stats import angular_similarity
from dipy.reconst.tests.test_dsi import sticks_and_ball_dummies
import nibabel as nib
from dipy.reconst.shore_cart import (shore_index_matrix, shore_phi_1d,
                                     shore_phi_3d, shore_psi_1d,
                                     shore_psi_3d, shore_phi_matrix,
                                     ShoreCartModel, ShoreCartFit,
                                     shore_laplace_delta,
                                     shore_laplace_s,
                                     shore_laplace_r,
                                     shore_laplace_l,
                                     shore_laplace_reg_matrix)
from dipy.io.gradients import read_bvals_bvecs



def test_shore():
    fetch_isbi2013_2shell()
    img, gtab = read_isbi2013_2shell()

    # load symmetric 724 sphere
    sphere = get_sphere('symmetric724')

    # load icosahedron sphere
    sphere2 = create_unit_sphere(5)
    data, golden_directions = SticksAndBall(gtab, d=0.0015,
                                            S0=100, angles=[(0, 0), (90, 0)],
                                            fractions=[50, 50], snr=None)
    asm = ShoreModel(gtab, radial_order=6,
                     zeta=700, lambdaN=1e-8, lambdaL=1e-8)
    # symmetric724
    asmfit = asm.fit(data)
    odf = asmfit.odf(sphere)

    directions, _, _ = peak_directions(odf, sphere, .35, 25)
    assert_equal(len(directions), 2)
    assert_almost_equal(
        angular_similarity(directions, golden_directions), 2, 1)

    # 5 subdivisions
    odf = asmfit.odf(sphere2)
    directions, _, _ = peak_directions(odf, sphere2, .35, 25)
    assert_equal(len(directions), 2)
    assert_almost_equal(
        angular_similarity(directions, golden_directions), 2, 1)

    sb_dummies = sticks_and_ball_dummies(gtab)
    for sbd in sb_dummies:
        data, golden_directions = sb_dummies[sbd]
        asmfit = asm.fit(data)
        odf = asmfit.odf(sphere2)
        directions, _, _ = peak_directions(odf, sphere2, .35, 25)
        if len(directions) <= 3:
            assert_equal(len(directions), len(golden_directions))
        if len(directions) > 3:
            assert_equal(gfa(odf) < 0.1, True)


def test_multivox_shore():
    fetch_sherbrooke_3shell()
    img, gtab = read_sherbrooke_3shell()

    test = img.get_data()
    data = test[45:65, 35:65, 33:34]
    radial_order = 4
    zeta = 700
    asm = ShoreModel(gtab, radial_order=radial_order,
                     zeta=zeta, lambdaN=1e-8, lambdaL=1e-8)
    asmfit = asm.fit(data)
    c_shore = asmfit.shore_coeff
    assert_equal(c_shore.shape[0:3], data.shape[0:3])
    assert_equal(np.alltrue(np.isreal(c_shore)), True)


def check_shore_index_size(radial_order):
    f = np.floor(radial_order / 2)
    return (f + 1) * (f + 2) * (4 * f + 3) / 6


def test_shore_cart():

    mat = shore_index_matrix(16)
    assert_equal(mat.shape[0], check_shore_index_size(16))

    phi = shore_phi_1d(50, 1.534, 0.001)

    assert_almost_equal(0.333504, np.real(phi), 6)

    phi3d = shore_phi_3d((3, 2, 9), (1.2, -2.35, 0.067),.004)

    assert_almost_equal(-0.000136642, phi3d, 8)

    psi = shore_psi_1d(2, .3, 0.32)

    assert_almost_equal(0.430482, psi, 6)

    psi3d = shore_psi_3d((4, 1, 5), (1.3, -2.5, 0.001), (0.3, 0.4, 0.5))

    assert_almost_equal(-2.42048e-12, psi3d, 5)


def test_shore_cart_matrix():

    fbvals, fbvecs = get_data('3shells_data')
    bvals, bvecs = read_bvals_bvecs(fbvals, fbvecs)
    gtab = gradient_table(bvals, bvecs)

    mat = shore_index_matrix(2)

    coeff = np.zeros(mat.shape[0])
    coeff[0] = 1

    zeta = 700.
    mu = 1/ (2 * np.pi * np.sqrt(zeta))

    pmat = shore_phi_matrix(radial_order=2, mu=mu, gtab=gtab,
                            tau=1 / (4 * np.pi ** 2))

    E = np.dot(pmat, coeff[:, None])
    E = np.squeeze(E)

    scm = ShoreCartModel(gtab, radial_order=2, mu=mu)

    scf = scm.fit(E)

    assert_almost_equal(scf.shore_coeff, coeff, 10)


    mat = shore_index_matrix(4)

    coeff = np.random.rand(mat.shape[0])

    pmat = shore_phi_matrix(radial_order=4, mu=mu, gtab=gtab,
                            tau=1 / (4 * np.pi ** 2))

    E = np.dot(pmat, coeff[:, None])
    E = np.squeeze(E)

    scm = ShoreCartModel(gtab, radial_order=4, mu=mu)

    scf = scm.fit(E)

    assert_almost_equal(scf.shore_coeff, coeff, 4)

    SNR = None
    S0 = 1

    mevals = np.array(([0.0015, 0.0003, 0.0003],
                       [0.0015, 0.0003, 0.0003]))

    data, sticks = multi_tensor(gtab, mevals, S0, angles=[(0, 0), (45, 0)],
                             fractions=[50, 50], snr=SNR)

    sphere = get_sphere('symmetric724')

    mevecs = [all_tensor_evecs(sticks[0]).T,
              all_tensor_evecs(sticks[1]).T]

    odf_gt = multi_tensor_odf(sphere.vertices, [0.5, 0.5], mevals, mevecs)

    scm = ShoreCartModel(gtab, radial_order=8, mu=mu, lambd=0)

    scf = scm.fit(data)

    odf = scf.odf(sphere, smoment=4)

    sm = ShoreModel(gtab, radial_order=8, zeta=700)

    smf = sm.fit(data)

    odf2 = smf.odf(sphere)


    scm = ShoreCartModel(gtab, radial_order=8, mu=mu, lambd=1)

    scf = scm.fit(data)

    odf3 = scf.odf(sphere, smoment=4)



    #assert_array_almost_equal(odf, odf_gt, 4)

    from dipy.viz import fvtk

    ren = fvtk.ren()

    odfs = np.zeros((4, 1, 1, sphere.vertices.shape[0]))
    odfs[0, 0, 0] = odf_gt
    odfs[1, 0, 0] = odf
    odfs[2, 0, 0] = odf2
    odfs[3, 0, 0] = odf3

    fvtk.add(ren, fvtk.sphere_funcs(odfs, sphere))
    fvtk.show(ren)


def test_shore_laplace():

    zeta = 700.
    #mu = 1/ (2 * np.pi * np.sqrt(zeta))
    mu = 1.5

    mat = shore_index_matrix(4)

    assert_almost_equal(shore_laplace_s(1, 1, 1.5), -0.18806319, 6)

    assert_almost_equal(shore_laplace_l(1, 3, 1.5), 20.459343469, 6)

    assert_almost_equal(shore_laplace_r(2, 6, 1.5), 7038.49129207, 6)

    assert_almost_equal(shore_laplace_delta(mat[2], mat[2], mu),
                        826.56401598, 6)

    assert_almost_equal(shore_laplace_delta(mat[1], mat[3], mu),
                        52.4803, 4)



    LR = shore_laplace_reg_matrix(2, 1.5)
    print LR


if __name__ == '__main__':
    # run_module_suite()
    test_shore_cart_matrix()
    #test_shore_laplace()
